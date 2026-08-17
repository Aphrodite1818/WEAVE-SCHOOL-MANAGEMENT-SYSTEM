"""Automatic durable CBT sync recording for academic domain mutations.

The hook runs on the synchronous Session wrapped by AsyncSession. Business
writes are flushed first; only then, at the outer transaction commit boundary,
we project the final state and record durable changes through ``CBTSyncRecorder``.
The sync log therefore commits or rolls back atomically with the business
transaction and works identically in API and worker processes.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
from app.modules.cbt.sync.projectors.registry import project_payload
from app.modules.cbt.sync.recorder import CBTSyncRecorder
from app.modules.cbt.sync.schemas import CBTSyncMutation
from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    AssessmentComponent,
    AssessmentScheme,
    TeacherAssignment,
)
from app.modules.students.models import Student, StudentEnrollment
from app.modules.subjects.models import Subject
from app.modules.teachers.models import TeacherAccount, TeacherMembership


@dataclass(slots=True)
class _PendingObject:
    obj: Any
    operation: CBTSyncOperation


@dataclass(frozen=True, slots=True)
class _PendingIdentity:
    tenant_id: uuid.UUID
    entity_type: CBTSyncEntityType
    entity_id: uuid.UUID
    operation: CBTSyncOperation


MODEL_ENTITY_TYPES: dict[type[Any], CBTSyncEntityType] = {
    AcademicLevel: CBTSyncEntityType.ACADEMIC_LEVEL,
    Department: CBTSyncEntityType.DEPARTMENT,
    ArmLabel: CBTSyncEntityType.ARM_LABEL,
    ClassRoom: CBTSyncEntityType.CLASS,
    ClassTermDepartmentAssignment: CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
    AcademicSession: CBTSyncEntityType.ACADEMIC_SESSION,
    AcademicTerm: CBTSyncEntityType.ACADEMIC_TERM,
    Subject: CBTSyncEntityType.SUBJECT,
    Curriculum: CBTSyncEntityType.CURRICULUM,
    CurriculumSubject: CBTSyncEntityType.CURRICULUM_SUBJECT,
    CurriculumOffering: CBTSyncEntityType.SUBJECT_OFFERING,
    AssessmentScheme: CBTSyncEntityType.ASSESSMENT_SCHEME,
    AssessmentComponent: CBTSyncEntityType.ASSESSMENT_COMPONENT,
    TeacherMembership: CBTSyncEntityType.TEACHER,
    TeacherAssignment: CBTSyncEntityType.TEACHER_ASSIGNMENT,
    StudentEnrollment: CBTSyncEntityType.STUDENT_ENROLLMENT,
}

_PENDING_KEY = "cbt_sync_pending_objects"
_TEACHER_ACCOUNT_KEY = "cbt_sync_teacher_accounts"
_STUDENT_KEY = "cbt_sync_students"
_INTERNAL_KEY = "cbt_sync_internal_write"
_REGISTERED = False


def _operation_for(session: Session, obj: Any) -> CBTSyncOperation | None:
    if obj in session.deleted:
        return CBTSyncOperation.DELETED
    if obj in session.new:
        return CBTSyncOperation.CREATED
    if obj in session.dirty and session.is_modified(obj, include_collections=False):
        return CBTSyncOperation.UPDATED
    return None


def _merge_operation(
    previous: CBTSyncOperation | None,
    current: CBTSyncOperation,
) -> CBTSyncOperation | None:
    if previous is None:
        return current
    if previous == CBTSyncOperation.CREATED:
        if current == CBTSyncOperation.DELETED:
            return None
        return CBTSyncOperation.CREATED
    if current == CBTSyncOperation.DELETED:
        return CBTSyncOperation.DELETED
    return CBTSyncOperation.UPDATED


def _collect_pending(session: Session) -> None:
    if session.info.get(_INTERNAL_KEY):
        return
    pending: OrderedDict[tuple[type[Any], int], _PendingObject] = session.info.setdefault(
        _PENDING_KEY,
        OrderedDict(),
    )
    candidates = list(session.new) + list(session.dirty) + list(session.deleted)
    for obj in candidates:
        operation = _operation_for(session, obj)
        if operation is None:
            continue
        if type(obj) in MODEL_ENTITY_TYPES:
            key = (type(obj), id(obj))
            previous = pending.get(key)
            merged = _merge_operation(
                previous.operation if previous else None,
                operation,
            )
            if merged is None:
                pending.pop(key, None)
            else:
                pending[key] = _PendingObject(obj=obj, operation=merged)
        elif isinstance(obj, TeacherAccount):
            session.info.setdefault(_TEACHER_ACCOUNT_KEY, set()).add(obj.id)
        elif isinstance(obj, Student):
            session.info.setdefault(_STUDENT_KEY, set()).add(obj.id)


def _identity_from_object(pending: _PendingObject) -> _PendingIdentity | None:
    obj = pending.obj
    tenant_id = getattr(obj, "tenant_id", None)
    entity_id = getattr(obj, "id", None)
    entity_type = MODEL_ENTITY_TYPES.get(type(obj))
    if tenant_id is None or entity_id is None or entity_type is None:
        return None
    return _PendingIdentity(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=pending.operation,
    )


def _append_identity(
    events: OrderedDict[
        tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID],
        _PendingIdentity,
    ],
    identity: _PendingIdentity,
) -> None:
    key = (identity.tenant_id, identity.entity_type, identity.entity_id)
    previous = events.get(key)
    merged = _merge_operation(
        previous.operation if previous else None,
        identity.operation,
    )
    if merged is None:
        events.pop(key, None)
        return
    events[key] = _PendingIdentity(
        tenant_id=identity.tenant_id,
        entity_type=identity.entity_type,
        entity_id=identity.entity_id,
        operation=merged,
    )


def _expand_account_updates(
    session: Session,
    events: OrderedDict[
        tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID],
        _PendingIdentity,
    ],
) -> None:
    account_ids = {
        value for value in session.info.get(_TEACHER_ACCOUNT_KEY, set()) if value
    }
    if not account_ids:
        return
    rows = session.execute(
        select(TeacherMembership.tenant_id, TeacherMembership.id).where(
            TeacherMembership.teacher_account_id.in_(account_ids)
        )
    ).all()
    for tenant_id, membership_id in rows:
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER,
                entity_id=membership_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )


def _expand_student_updates(
    session: Session,
    events: OrderedDict[
        tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID],
        _PendingIdentity,
    ],
) -> None:
    student_ids = {value for value in session.info.get(_STUDENT_KEY, set()) if value}
    if not student_ids:
        return
    rows = session.execute(
        select(StudentEnrollment.tenant_id, StudentEnrollment.id).where(
            StudentEnrollment.student_id.in_(student_ids),
            StudentEnrollment.is_current.is_(True),
        )
    ).all()
    for tenant_id, enrollment_id in rows:
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.STUDENT_ENROLLMENT,
                entity_id=enrollment_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )


def _offering_ids_for_tenant(session: Session, tenant_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.execute(
            select(CurriculumOffering.id).where(
                CurriculumOffering.tenant_id == tenant_id
            )
        ).scalars()
    )


def _expand_derived_offerings(
    session: Session,
    pending_objects: list[_PendingObject],
    events: OrderedDict[
        tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID],
        _PendingIdentity,
    ],
) -> None:
    """Refresh computed offering eligibility after structural mutations.

    Eligibility is a projection of curriculum, class specialization and current
    student enrollment. For these relatively infrequent administrative mutations,
    refreshing every offering for the affected tenant is intentionally preferred
    to trying to infer a post-flush old/new scope and risking stale CBT candidates.
    Curriculum-subject-only changes can remain narrowly scoped.
    """

    tenant_wide_refreshes: set[uuid.UUID] = set()
    narrow_subjects: list[tuple[uuid.UUID, uuid.UUID]] = []

    for pending in pending_objects:
        obj = pending.obj
        tenant_id = getattr(obj, "tenant_id", None)
        if tenant_id is None:
            continue
        if isinstance(
            obj,
            (
                ClassRoom,
                Department,
                ClassTermDepartmentAssignment,
                Curriculum,
                StudentEnrollment,
            ),
        ):
            tenant_wide_refreshes.add(tenant_id)
        elif isinstance(obj, CurriculumSubject):
            narrow_subjects.append((tenant_id, obj.id))

    for tenant_id in tenant_wide_refreshes:
        for offering_id in _offering_ids_for_tenant(session, tenant_id):
            _append_identity(
                events,
                _PendingIdentity(
                    tenant_id=tenant_id,
                    entity_type=CBTSyncEntityType.SUBJECT_OFFERING,
                    entity_id=offering_id,
                    operation=CBTSyncOperation.UPDATED,
                ),
            )

    for tenant_id, curriculum_subject_id in narrow_subjects:
        if tenant_id in tenant_wide_refreshes:
            continue
        offering_ids = session.execute(
            select(CurriculumOffering.id).where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
            )
        ).scalars()
        for offering_id in offering_ids:
            _append_identity(
                events,
                _PendingIdentity(
                    tenant_id=tenant_id,
                    entity_type=CBTSyncEntityType.SUBJECT_OFFERING,
                    entity_id=offering_id,
                    operation=CBTSyncOperation.UPDATED,
                ),
            )


def _materialize_events(session: Session) -> list[_PendingIdentity]:
    events: OrderedDict[
        tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID],
        _PendingIdentity,
    ] = OrderedDict()
    pending_objects = list(
        session.info.get(_PENDING_KEY, OrderedDict()).values()
    )
    for pending in pending_objects:
        identity = _identity_from_object(pending)
        if identity is not None:
            _append_identity(events, identity)
    _expand_account_updates(session, events)
    _expand_student_updates(session, events)
    _expand_derived_offerings(session, pending_objects, events)
    return list(events.values())


def _normalized_mutation(
    session: Session,
    identity: _PendingIdentity,
) -> CBTSyncMutation | None:
    if identity.operation == CBTSyncOperation.DELETED:
        return CBTSyncMutation(
            entity_type=identity.entity_type,
            entity_id=identity.entity_id,
            operation=CBTSyncOperation.DELETED,
            schema_version=2,
            payload=None,
        )

    payload = project_payload(
        session,
        tenant_id=identity.tenant_id,
        entity_type=identity.entity_type,
        entity_id=identity.entity_id,
    )
    if payload is None:
        if identity.operation == CBTSyncOperation.CREATED:
            return None
        return CBTSyncMutation(
            entity_type=identity.entity_type,
            entity_id=identity.entity_id,
            operation=CBTSyncOperation.DELETED,
            schema_version=2,
            payload=None,
        )
    return CBTSyncMutation(
        entity_type=identity.entity_type,
        entity_id=identity.entity_id,
        operation=identity.operation,
        schema_version=2,
        payload=payload,
    )


def _write_changes(session: Session, identities: list[_PendingIdentity]) -> None:
    if not identities:
        return
    if session.connection().dialect.name != "postgresql":
        # Production ordering/notification semantics require PostgreSQL. Unit tests
        # that use SQLite exercise projection and event materialization separately.
        return

    for identity in identities:
        mutation = _normalized_mutation(session, identity)
        if mutation is None:
            continue
        CBTSyncRecorder.record_sync(
            session,
            tenant_id=identity.tenant_id,
            mutation=mutation,
        )


def _clear_state(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
    session.info.pop(_TEACHER_ACCOUNT_KEY, None)
    session.info.pop(_STUDENT_KEY, None)
    session.info.pop(_INTERNAL_KEY, None)


def _before_flush(session: Session, _flush_context: Any, _instances: Any) -> None:
    _collect_pending(session)


def _before_commit(session: Session) -> None:
    # Savepoint commits occur inside progression/bulk workflows. Keep collecting
    # until the outer transaction so one durable sequence describes the true
    # business commit boundary.
    if session.in_nested_transaction() or session.info.get(_INTERNAL_KEY):
        return
    _collect_pending(session)
    has_pending = bool(
        session.info.get(_PENDING_KEY)
        or session.info.get(_TEACHER_ACCOUNT_KEY)
        or session.info.get(_STUDENT_KEY)
    )
    if not has_pending:
        return

    session.info[_INTERNAL_KEY] = True
    try:
        session.flush()
        identities = _materialize_events(session)
        _write_changes(session, identities)
    finally:
        session.info.pop(_INTERNAL_KEY, None)


def register_cbt_sync_model_events() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "before_commit", _before_commit)
    event.listen(Session, "after_commit", _clear_state)
    event.listen(Session, "after_rollback", _clear_state)
    _REGISTERED = True


register_cbt_sync_model_events()
