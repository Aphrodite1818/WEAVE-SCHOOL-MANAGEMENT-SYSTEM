"""Automatic durable CBT sync recording for academic domain mutations.

The hook runs on the synchronous Session wrapped by AsyncSession. Business
writes are flushed first; only then, at the outer transaction commit boundary,
we project the final state and record durable changes through ``CBTSyncRecorder``.
The sync log therefore commits or rolls back atomically with the business
transaction and works identically in API and worker processes.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict, defaultdict
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
from app.modules.tenant_admins.models import TenantAdmin
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
    TenantAdmin: CBTSyncEntityType.ADMIN,
    TeacherMembership: CBTSyncEntityType.TEACHER,
    TeacherAssignment: CBTSyncEntityType.TEACHER_ASSIGNMENT,
    StudentEnrollment: CBTSyncEntityType.STUDENT_ENROLLMENT,
}

ENTITY_MODELS: dict[CBTSyncEntityType, type[Any]] = {
    entity_type: model for model, entity_type in MODEL_ENTITY_TYPES.items()
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
            merged = _merge_operation(previous.operation if previous else None, operation)
            if merged is None:
                pending.pop(key, None)
            else:
                pending[key] = _PendingObject(obj=obj, operation=merged)
        elif isinstance(obj, TeacherAccount):
            if obj.id:
                session.info.setdefault(_TEACHER_ACCOUNT_KEY, set()).add(obj.id)
        elif isinstance(obj, Student):
            if obj.id:
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
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    identity: _PendingIdentity,
) -> None:
    key = (identity.tenant_id, identity.entity_type, identity.entity_id)
    previous = events.get(key)
    merged = _merge_operation(previous.operation if previous else None, identity.operation)
    if merged is None:
        events.pop(key, None)
        return
    events[key] = _PendingIdentity(
        tenant_id=identity.tenant_id,
        entity_type=identity.entity_type,
        entity_id=identity.entity_id,
        operation=merged,
    )


def _append_refreshes(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    *,
    tenant_id: uuid.UUID,
    entity_type: CBTSyncEntityType,
) -> None:
    model = ENTITY_MODELS[entity_type]
    entity_ids = session.execute(select(model.id).where(model.tenant_id == tenant_id)).scalars()
    for entity_id in entity_ids:
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )


def _expand_account_updates(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
) -> set[uuid.UUID]:
    """Refresh tenant memberships derived from a global teacher-account mutation."""

    account_ids = {value for value in session.info.get(_TEACHER_ACCOUNT_KEY, set()) if value}
    if not account_ids:
        return set()
    rows = session.execute(
        select(TeacherMembership.tenant_id, TeacherMembership.id).where(
            TeacherMembership.teacher_account_id.in_(account_ids)
        )
    ).all()
    tenant_ids: set[uuid.UUID] = set()
    for tenant_id, membership_id in rows:
        tenant_ids.add(tenant_id)
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER,
                entity_id=membership_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )
    return tenant_ids


def _expand_student_updates(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
) -> set[uuid.UUID]:
    """Refresh enrollment projections derived from student lifecycle mutations."""

    student_ids = {value for value in session.info.get(_STUDENT_KEY, set()) if value}
    if not student_ids:
        return set()

    tenant_ids: set[uuid.UUID] = set()
    rows = session.execute(
        select(StudentEnrollment.tenant_id, StudentEnrollment.id).where(
            StudentEnrollment.student_id.in_(student_ids)
        )
    ).all()
    for tenant_id, enrollment_id in rows:
        tenant_ids.add(tenant_id)
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.STUDENT_ENROLLMENT,
                entity_id=enrollment_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )

    # Graduation/archival can remove the last visible enrollment in the same
    # transaction. Keep the tenant as an offering-eligibility invalidation source.
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(obj, Student) and obj.id in student_ids and obj.tenant_id:
            tenant_ids.add(obj.tenant_id)
    return tenant_ids


def _expand_derived_contracts(
    session: Session,
    pending_objects: list[_PendingObject],
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    *,
    student_refresh_tenants: set[uuid.UUID],
    teacher_refresh_tenants: set[uuid.UUID],
) -> None:
    """Refresh every projector whose visibility/payload depends on changed state.

    The dependency graph is intentionally explicit. Academic structure changes are
    low-frequency administrative writes, so a tenant-scoped refresh is safer than
    attempting to reconstruct every old/new foreign-key path. ``project_payload``
    remains the sole authority: a refresh becomes an update when the entity is still
    visible and a delete when its parent/configuration makes it disappear.
    """

    refreshes: dict[CBTSyncEntityType, set[uuid.UUID]] = defaultdict(set)
    for tenant_id in student_refresh_tenants:
        refreshes[CBTSyncEntityType.SUBJECT_OFFERING].add(tenant_id)
    for tenant_id in teacher_refresh_tenants:
        refreshes[CBTSyncEntityType.TEACHER_ASSIGNMENT].add(tenant_id)

    for pending in pending_objects:
        obj = pending.obj
        tenant_id = getattr(obj, "tenant_id", None)
        if tenant_id is None:
            continue

        if isinstance(obj, AcademicLevel):
            for entity_type in (
                CBTSyncEntityType.DEPARTMENT,
                CBTSyncEntityType.CLASS,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.CURRICULUM,
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ArmLabel):
            for entity_type in (
                CBTSyncEntityType.CLASS,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Department):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ClassRoom):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ClassTermDepartmentAssignment):
            refreshes[CBTSyncEntityType.SUBJECT_OFFERING].add(tenant_id)
            refreshes[CBTSyncEntityType.TEACHER_ASSIGNMENT].add(tenant_id)
        elif isinstance(obj, AcademicSession):
            for entity_type in (
                CBTSyncEntityType.ACADEMIC_TERM,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, AcademicTerm):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Subject):
            for entity_type in (
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Curriculum):
            for entity_type in (
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, CurriculumSubject):
            refreshes[CBTSyncEntityType.SUBJECT_OFFERING].add(tenant_id)
            refreshes[CBTSyncEntityType.TEACHER_ASSIGNMENT].add(tenant_id)
        elif isinstance(obj, CurriculumOffering):
            refreshes[CBTSyncEntityType.TEACHER_ASSIGNMENT].add(tenant_id)
        elif isinstance(obj, AssessmentScheme):
            refreshes[CBTSyncEntityType.ASSESSMENT_COMPONENT].add(tenant_id)
        elif isinstance(obj, TeacherMembership):
            refreshes[CBTSyncEntityType.TEACHER_ASSIGNMENT].add(tenant_id)
        elif isinstance(obj, StudentEnrollment):
            refreshes[CBTSyncEntityType.SUBJECT_OFFERING].add(tenant_id)

    for entity_type, tenant_ids in refreshes.items():
        for tenant_id in tenant_ids:
            _append_refreshes(
                session,
                events,
                tenant_id=tenant_id,
                entity_type=entity_type,
            )


def _materialize_events(session: Session) -> list[_PendingIdentity]:
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity] = (
        OrderedDict()
    )
    pending_objects = list(session.info.get(_PENDING_KEY, OrderedDict()).values())
    for pending in pending_objects:
        identity = _identity_from_object(pending)
        if identity is not None:
            _append_identity(events, identity)
    teacher_refresh_tenants = _expand_account_updates(session, events)
    student_refresh_tenants = _expand_student_updates(session, events)
    _expand_derived_contracts(
        session,
        pending_objects,
        events,
        student_refresh_tenants=student_refresh_tenants,
        teacher_refresh_tenants=teacher_refresh_tenants,
    )
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
