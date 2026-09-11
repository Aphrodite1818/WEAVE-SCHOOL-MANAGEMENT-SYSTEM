"""Automatic durable CBT sync recording for academic domain mutations.

The hook runs on the synchronous Session wrapped by AsyncSession. Business
writes are flushed first; only then, at the outer transaction commit boundary,
we project the final state, normalize visibility changes, order them by
relationship dependency and append one batched durable cursor range.
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
from app.modules.cbt.sync.schemas import CBTSyncMutation, SYNC_SCHEMA_VERSION
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumSubject,
    CurriculumSubjectDepartment,
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


@dataclass(slots=True)
class _SavepointJournal:
    pending_before: dict[tuple[type[Any], int], _PendingObject | None]
    teacher_accounts_added: set[uuid.UUID]
    students_added: set[uuid.UUID]


@dataclass(frozen=True, slots=True)
class _PendingIdentity:
    tenant_id: uuid.UUID
    entity_type: CBTSyncEntityType
    entity_id: uuid.UUID
    operation: CBTSyncOperation


MODEL_ENTITY_TYPES: dict[type[Any], CBTSyncEntityType] = {
    AcademicLevel: CBTSyncEntityType.ACADEMIC_LEVEL,
    Department: CBTSyncEntityType.DEPARTMENT,
    AcademicLevelDepartment: CBTSyncEntityType.DEPARTMENT,
    ArmLabel: CBTSyncEntityType.ARM_LABEL,
    ClassRoom: CBTSyncEntityType.CLASS,
    ClassTermDepartmentAssignment: CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
    AcademicSession: CBTSyncEntityType.ACADEMIC_SESSION,
    AcademicTerm: CBTSyncEntityType.ACADEMIC_TERM,
    Subject: CBTSyncEntityType.SUBJECT,
    Curriculum: CBTSyncEntityType.CURRICULUM,
    CurriculumSubject: CBTSyncEntityType.CURRICULUM_SUBJECT,
    CurriculumSubjectDepartment: CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
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

# Upserts are parent-first. Tombstones use reverse dependency order.
_UPSERT_ORDER = (
    CBTSyncEntityType.ACADEMIC_SESSION,
    CBTSyncEntityType.ACADEMIC_TERM,
    CBTSyncEntityType.ACADEMIC_LEVEL,
    CBTSyncEntityType.ARM_LABEL,
    CBTSyncEntityType.DEPARTMENT,
    CBTSyncEntityType.CLASS,
    CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
    CBTSyncEntityType.SUBJECT,
    CBTSyncEntityType.CURRICULUM,
    CBTSyncEntityType.CURRICULUM_SUBJECT,
    CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
    CBTSyncEntityType.ASSESSMENT_SCHEME,
    CBTSyncEntityType.ASSESSMENT_COMPONENT,
    CBTSyncEntityType.ADMIN,
    CBTSyncEntityType.TEACHER,
    CBTSyncEntityType.STUDENT_ENROLLMENT,
    CBTSyncEntityType.TEACHER_ASSIGNMENT,
)
_ORDER_RANK = {entity_type: index for index, entity_type in enumerate(_UPSERT_ORDER)}

_PENDING_KEY = "cbt_sync_pending_objects"
_TEACHER_ACCOUNT_KEY = "cbt_sync_teacher_accounts"
_STUDENT_KEY = "cbt_sync_students"
_INTERNAL_KEY = "cbt_sync_internal_write"
_SAVEPOINT_JOURNALS_KEY = "cbt_sync_savepoint_journals"
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


def _current_savepoint_journal(session: Session) -> _SavepointJournal | None:
    transaction = session.get_nested_transaction()
    if transaction is None:
        return None
    journals: dict[Any, _SavepointJournal] = session.info.setdefault(_SAVEPOINT_JOURNALS_KEY, {})
    return journals.setdefault(
        transaction,
        _SavepointJournal(
            pending_before={},
            teacher_accounts_added=set(),
            students_added=set(),
        ),
    )


def _restore_savepoint_journal(session: Session, transaction: Any) -> None:
    journals: dict[Any, _SavepointJournal] | None = session.info.get(_SAVEPOINT_JOURNALS_KEY)
    if not journals:
        return
    journal = journals.pop(transaction, None)
    if journal is None:
        return

    pending: OrderedDict[tuple[type[Any], int], _PendingObject] = session.info.setdefault(
        _PENDING_KEY, OrderedDict()
    )
    for key, previous in journal.pending_before.items():
        if previous is None:
            pending.pop(key, None)
        else:
            pending[key] = previous
    if not pending:
        session.info.pop(_PENDING_KEY, None)

    teacher_accounts: set[uuid.UUID] | None = session.info.get(_TEACHER_ACCOUNT_KEY)
    if teacher_accounts is not None:
        teacher_accounts.difference_update(journal.teacher_accounts_added)
        if not teacher_accounts:
            session.info.pop(_TEACHER_ACCOUNT_KEY, None)

    students: set[uuid.UUID] | None = session.info.get(_STUDENT_KEY)
    if students is not None:
        students.difference_update(journal.students_added)
        if not students:
            session.info.pop(_STUDENT_KEY, None)

    if not journals:
        session.info.pop(_SAVEPOINT_JOURNALS_KEY, None)


def _collect_pending(session: Session) -> None:
    if session.info.get(_INTERNAL_KEY):
        return
    pending: OrderedDict[tuple[type[Any], int], _PendingObject] = session.info.setdefault(
        _PENDING_KEY, OrderedDict()
    )
    journal = _current_savepoint_journal(session)
    candidates = list(session.new) + list(session.dirty) + list(session.deleted)
    for obj in candidates:
        operation = _operation_for(session, obj)
        if operation is None:
            continue
        if type(obj) in MODEL_ENTITY_TYPES:
            key = (type(obj), id(obj))
            if journal is not None and key not in journal.pending_before:
                journal.pending_before[key] = pending.get(key)
            previous = pending.get(key)
            merged = _merge_operation(previous.operation if previous else None, operation)
            if merged is None:
                pending.pop(key, None)
            else:
                pending[key] = _PendingObject(obj=obj, operation=merged)
        elif isinstance(obj, TeacherAccount) and obj.id:
            teacher_accounts: set[uuid.UUID] = session.info.setdefault(_TEACHER_ACCOUNT_KEY, set())
            if journal is not None and obj.id not in teacher_accounts:
                journal.teacher_accounts_added.add(obj.id)
            teacher_accounts.add(obj.id)
        elif isinstance(obj, Student) and obj.id:
            students: set[uuid.UUID] = session.info.setdefault(_STUDENT_KEY, set())
            if journal is not None and obj.id not in students:
                journal.students_added.add(obj.id)
            students.add(obj.id)


def _identity_from_object(pending: _PendingObject) -> _PendingIdentity | None:
    obj = pending.obj
    # Canonical departments are a cloud-side pool. CBT consumes the exact
    # AcademicLevelDepartment identity, so pool mutations only trigger refreshes.
    if isinstance(obj, Department):
        return None
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


def _append_refresh_ids(
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    *,
    tenant_id: uuid.UUID,
    entity_type: CBTSyncEntityType,
    entity_ids: Any,
) -> None:
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


def _append_refreshes(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    *,
    tenant_id: uuid.UUID,
    entity_type: CBTSyncEntityType,
) -> None:
    model = ENTITY_MODELS[entity_type]
    entity_ids = session.execute(select(model.id).where(model.tenant_id == tenant_id)).scalars()
    _append_refresh_ids(
        events,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_ids=entity_ids,
    )


def _expand_account_updates(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
) -> None:
    account_ids = {value for value in session.info.get(_TEACHER_ACCOUNT_KEY, set()) if value}
    if not account_ids:
        return
    rows = session.execute(
        select(TeacherMembership.tenant_id, TeacherMembership.id).where(
            TeacherMembership.teacher_account_id.in_(account_ids)
        )
    ).all()
    membership_ids: list[uuid.UUID] = []
    for tenant_id, membership_id in rows:
        membership_ids.append(membership_id)
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER,
                entity_id=membership_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )
    if not membership_ids:
        return
    assignment_rows = session.execute(
        select(TeacherAssignment.tenant_id, TeacherAssignment.id).where(
            TeacherAssignment.teacher_membership_id.in_(membership_ids)
        )
    ).all()
    for tenant_id, assignment_id in assignment_rows:
        _append_identity(
            events,
            _PendingIdentity(
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
                entity_id=assignment_id,
                operation=CBTSyncOperation.UPDATED,
            ),
        )


def _expand_student_updates(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
) -> None:
    student_ids = {value for value in session.info.get(_STUDENT_KEY, set()) if value}
    if not student_ids:
        return
    rows = session.execute(
        select(StudentEnrollment.tenant_id, StudentEnrollment.id).where(
            StudentEnrollment.student_id.in_(student_ids)
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


def _refresh_assignments_for_membership(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    membership: TeacherMembership,
) -> None:
    ids = session.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.tenant_id == membership.tenant_id,
            TeacherAssignment.teacher_membership_id == membership.id,
        )
    ).scalars()
    _append_refresh_ids(
        events,
        tenant_id=membership.tenant_id,
        entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
        entity_ids=ids,
    )


def _refresh_assignments_for_scope(
    session: Session,
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
    scope: CurriculumSubjectDepartment,
) -> None:
    ids = session.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.tenant_id == scope.tenant_id,
            TeacherAssignment.curriculum_subject_id == scope.curriculum_subject_id,
        )
    ).scalars()
    _append_refresh_ids(
        events,
        tenant_id=scope.tenant_id,
        entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
        entity_ids=ids,
    )


def _expand_derived_contracts(
    session: Session,
    pending_objects: list[_PendingObject],
    events: OrderedDict[tuple[uuid.UUID, CBTSyncEntityType, uuid.UUID], _PendingIdentity],
) -> None:
    """Refresh projections whose visible state is derived from another model."""

    refreshes: dict[CBTSyncEntityType, set[uuid.UUID]] = defaultdict(set)

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
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ArmLabel):
            for entity_type in (
                CBTSyncEntityType.CLASS,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Department):
            for entity_type in (
                CBTSyncEntityType.DEPARTMENT,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, AcademicLevelDepartment):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ClassRoom):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, ClassTermDepartmentAssignment):
            assignment_ids = session.execute(
                select(TeacherAssignment.id).where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.class_id == obj.class_id,
                )
            ).scalars()
            _append_refresh_ids(
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
                entity_ids=assignment_ids,
            )
        elif isinstance(obj, AcademicSession):
            for entity_type in (
                CBTSyncEntityType.ACADEMIC_TERM,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, AcademicTerm):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Subject):
            for entity_type in (
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, Curriculum):
            for entity_type in (
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                refreshes[entity_type].add(tenant_id)
        elif isinstance(obj, CurriculumSubject):
            scope_ids = session.execute(
                select(CurriculumSubjectDepartment.id).where(
                    CurriculumSubjectDepartment.tenant_id == tenant_id,
                    CurriculumSubjectDepartment.curriculum_subject_id == obj.id,
                )
            ).scalars()
            _append_refresh_ids(
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                entity_ids=scope_ids,
            )
            assignment_ids = session.execute(
                select(TeacherAssignment.id).where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.curriculum_subject_id == obj.id,
                )
            ).scalars()
            _append_refresh_ids(
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
                entity_ids=assignment_ids,
            )
        elif isinstance(obj, CurriculumSubjectDepartment):
            _refresh_assignments_for_scope(session, events, obj)
        elif isinstance(obj, AssessmentScheme):
            refreshes[CBTSyncEntityType.ASSESSMENT_COMPONENT].add(tenant_id)
        elif isinstance(obj, TeacherMembership):
            _refresh_assignments_for_membership(session, events, obj)

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
    _expand_account_updates(session, events)
    _expand_student_updates(session, events)
    _expand_derived_contracts(session, pending_objects, events)
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
            schema_version=SYNC_SCHEMA_VERSION,
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
            schema_version=SYNC_SCHEMA_VERSION,
            payload=None,
        )
    return CBTSyncMutation(
        entity_type=identity.entity_type,
        entity_id=identity.entity_id,
        operation=identity.operation,
        schema_version=SYNC_SCHEMA_VERSION,
        payload=payload,
    )


def _mutation_sort_key(mutation: CBTSyncMutation) -> tuple[int, int, str]:
    rank = _ORDER_RANK[mutation.entity_type]
    if mutation.operation == CBTSyncOperation.DELETED:
        return (0, -rank, str(mutation.entity_id))
    return (1, rank, str(mutation.entity_id))


def _write_changes(session: Session, identities: list[_PendingIdentity]) -> int:
    if not identities:
        return 0
    if session.connection().dialect.name != "postgresql":
        return 0

    by_tenant: dict[uuid.UUID, list[CBTSyncMutation]] = defaultdict(list)
    for identity in identities:
        mutation = _normalized_mutation(session, identity)
        if mutation is not None:
            by_tenant[identity.tenant_id].append(mutation)

    written = 0
    for tenant_id in sorted(by_tenant, key=str):
        mutations = sorted(by_tenant[tenant_id], key=_mutation_sort_key)
        CBTSyncRecorder.record_many_sync(
            session,
            tenant_id=tenant_id,
            mutations=mutations,
        )
        written += len(mutations)
    return written


def _clear_collected_state(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
    session.info.pop(_TEACHER_ACCOUNT_KEY, None)
    session.info.pop(_STUDENT_KEY, None)
    session.info.pop(_SAVEPOINT_JOURNALS_KEY, None)


def _clear_state(session: Session) -> None:
    _clear_collected_state(session)
    session.info.pop(_INTERNAL_KEY, None)


def prepare_cbt_sync_commit(session: Session) -> int:
    """Materialize and consume pending CBT mutations before the outer commit."""

    if session.in_nested_transaction() or session.info.get(_INTERNAL_KEY):
        return 0

    _collect_pending(session)
    has_pending = bool(
        session.info.get(_PENDING_KEY)
        or session.info.get(_TEACHER_ACCOUNT_KEY)
        or session.info.get(_STUDENT_KEY)
    )
    if not has_pending:
        return 0

    session.info[_INTERNAL_KEY] = True
    try:
        session.flush()
        identities = _materialize_events(session)
        written = _write_changes(session, identities)
        _clear_collected_state(session)
        return written
    finally:
        session.info.pop(_INTERNAL_KEY, None)


def _before_flush(session: Session, _flush_context: Any, _instances: Any) -> None:
    _collect_pending(session)


def _before_commit(session: Session) -> None:
    prepare_cbt_sync_commit(session)


def _after_soft_rollback(session: Session, previous_transaction: Any) -> None:
    if getattr(previous_transaction, "nested", False):
        _restore_savepoint_journal(session, previous_transaction)
    elif getattr(previous_transaction, "parent", None) is None:
        _clear_state(session)


def _after_transaction_end(session: Session, transaction: Any) -> None:
    if getattr(transaction, "parent", None) is None:
        _clear_state(session)


def register_cbt_sync_model_events() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "before_commit", _before_commit)
    event.listen(Session, "after_soft_rollback", _after_soft_rollback)
    event.listen(Session, "after_transaction_end", _after_transaction_end)
    _REGISTERED = True


register_cbt_sync_model_events()
