from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from app.modules.cbt.sync import model_events
from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
from app.modules.cbt.sync.schemas import CBTSyncMutation, SYNC_SCHEMA_VERSION
from app.modules.classes.models import AcademicLevel
from app.modules.students.models import Student


class _Transaction:
    def __init__(self, *, nested: bool, parent: object | None) -> None:
        self.nested = nested
        self.parent = parent


class _FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}
        self.new: list[object] = []
        self.dirty: list[object] = []
        self.deleted: list[object] = []
        self.nested_transaction: object | None = None
        self.flush_count = 0

    def is_modified(self, _obj: object, *, include_collections: bool = False) -> bool:
        return True

    def get_nested_transaction(self):
        return self.nested_transaction

    def in_nested_transaction(self) -> bool:
        return self.nested_transaction is not None

    def flush(self) -> None:
        self.flush_count += 1


def _level() -> AcademicLevel:
    level = AcademicLevel()
    level.id = uuid4()
    level.tenant_id = uuid4()
    return level


def _student() -> Student:
    student = Student()
    student.id = uuid4()
    student.tenant_id = uuid4()
    return student


def _mutation(
    entity_type: CBTSyncEntityType,
    operation: CBTSyncOperation,
) -> CBTSyncMutation:
    return CBTSyncMutation(
        entity_type=entity_type,
        entity_id=uuid4(),
        operation=operation,
        schema_version=SYNC_SCHEMA_VERSION,
        payload=None if operation == CBTSyncOperation.DELETED else {"id": str(uuid4())},
    )


def test_successful_savepoint_preserves_pending_mutations_until_outer_end() -> None:
    session = _FakeSession()
    transaction = _Transaction(nested=True, parent=object())
    session.nested_transaction = transaction
    level = _level()
    session.new = [level]

    model_events._collect_pending(session)  # type: ignore[arg-type]
    model_events._after_transaction_end(session, transaction)  # type: ignore[arg-type]

    pending = session.info[model_events._PENDING_KEY]
    assert len(pending) == 1  # type: ignore[arg-type]

    session.nested_transaction = None
    outer_transaction = _Transaction(nested=False, parent=None)
    model_events._after_transaction_end(session, outer_transaction)  # type: ignore[arg-type]
    assert model_events._PENDING_KEY not in session.info
    assert model_events._SAVEPOINT_JOURNALS_KEY not in session.info


def test_failed_savepoint_restores_only_state_created_inside_it() -> None:
    session = _FakeSession()
    first_level = _level()
    session.new = [first_level]
    model_events._collect_pending(session)  # type: ignore[arg-type]

    transaction = _Transaction(nested=True, parent=object())
    session.nested_transaction = transaction
    second_level = _level()
    session.new = [second_level]
    model_events._collect_pending(session)  # type: ignore[arg-type]

    pending = session.info[model_events._PENDING_KEY]
    assert len(pending) == 2  # type: ignore[arg-type]

    model_events._after_soft_rollback(session, transaction)  # type: ignore[arg-type]

    pending = session.info[model_events._PENDING_KEY]
    assert len(pending) == 1  # type: ignore[arg-type]
    remaining = next(iter(pending.values()))  # type: ignore[union-attr]
    assert remaining.obj is first_level


def test_failed_savepoint_restores_student_refresh_tracking() -> None:
    session = _FakeSession()
    first_student = _student()
    session.new = [first_student]
    model_events._collect_pending(session)  # type: ignore[arg-type]

    transaction = _Transaction(nested=True, parent=object())
    session.nested_transaction = transaction
    second_student = _student()
    session.new = [second_student]
    model_events._collect_pending(session)  # type: ignore[arg-type]

    model_events._after_soft_rollback(session, transaction)  # type: ignore[arg-type]

    tracked_students = session.info[model_events._STUDENT_KEY]
    assert tracked_students == {first_student.id}


def test_outer_rollback_clears_all_pending_state() -> None:
    session = _FakeSession()
    session.new = [_level(), _student()]
    model_events._collect_pending(session)  # type: ignore[arg-type]

    outer_transaction = _Transaction(nested=False, parent=None)
    model_events._after_soft_rollback(session, outer_transaction)  # type: ignore[arg-type]

    assert model_events._PENDING_KEY not in session.info
    assert model_events._STUDENT_KEY not in session.info
    assert model_events._SAVEPOINT_JOURNALS_KEY not in session.info


def test_prepare_commit_materializes_and_consumes_pending_state() -> None:
    session = _FakeSession()
    level = _level()
    session.new = [level]
    identity = model_events._PendingIdentity(
        tenant_id=level.tenant_id,
        entity_type=CBTSyncEntityType.ACADEMIC_LEVEL,
        entity_id=level.id,
        operation=CBTSyncOperation.CREATED,
    )

    with (
        patch.object(model_events, "_materialize_events", return_value=[identity]),
        patch.object(model_events, "_write_changes", return_value=1) as write_changes,
    ):
        written = model_events.prepare_cbt_sync_commit(session)  # type: ignore[arg-type]

    assert written == 1
    assert session.flush_count == 1
    write_changes.assert_called_once_with(session, [identity])
    assert model_events._PENDING_KEY not in session.info
    assert model_events._TEACHER_ACCOUNT_KEY not in session.info
    assert model_events._STUDENT_KEY not in session.info
    assert model_events._SAVEPOINT_JOURNALS_KEY not in session.info
    assert model_events._INTERNAL_KEY not in session.info


def test_prepare_commit_is_deferred_while_inside_savepoint() -> None:
    session = _FakeSession()
    session.nested_transaction = _Transaction(nested=True, parent=object())
    session.new = [_level()]

    written = model_events.prepare_cbt_sync_commit(session)  # type: ignore[arg-type]

    assert written == 0
    assert session.flush_count == 0


def test_invisible_lifecycle_updates_become_explicit_v3_tombstones() -> None:
    tenant_id = uuid4()
    for entity_type in (
        CBTSyncEntityType.STUDENT_ENROLLMENT,
        CBTSyncEntityType.TEACHER_ASSIGNMENT,
    ):
        identity = model_events._PendingIdentity(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=uuid4(),
            operation=CBTSyncOperation.UPDATED,
        )
        with patch.object(model_events, "project_payload", return_value=None):
            mutation = model_events._normalized_mutation(object(), identity)  # type: ignore[arg-type]

        assert mutation is not None
        assert mutation.entity_type == entity_type
        assert mutation.operation == CBTSyncOperation.DELETED
        assert mutation.payload is None
        assert mutation.schema_version == 3


def test_replacement_tombstones_sort_before_new_live_rows() -> None:
    old_assignment = _mutation(
        CBTSyncEntityType.TEACHER_ASSIGNMENT,
        CBTSyncOperation.DELETED,
    )
    new_assignment = _mutation(
        CBTSyncEntityType.TEACHER_ASSIGNMENT,
        CBTSyncOperation.CREATED,
    )
    old_enrollment = _mutation(
        CBTSyncEntityType.STUDENT_ENROLLMENT,
        CBTSyncOperation.DELETED,
    )
    new_enrollment = _mutation(
        CBTSyncEntityType.STUDENT_ENROLLMENT,
        CBTSyncOperation.CREATED,
    )

    ordered = sorted(
        [new_assignment, new_enrollment, old_assignment, old_enrollment],
        key=model_events._mutation_sort_key,
    )

    assert [item.operation for item in ordered[:2]] == [
        CBTSyncOperation.DELETED,
        CBTSyncOperation.DELETED,
    ]
    assert old_assignment in ordered[:2]
    assert old_enrollment in ordered[:2]


def test_live_upserts_sort_parent_before_child() -> None:
    session = _mutation(CBTSyncEntityType.ACADEMIC_SESSION, CBTSyncOperation.CREATED)
    term = _mutation(CBTSyncEntityType.ACADEMIC_TERM, CBTSyncOperation.CREATED)
    level = _mutation(CBTSyncEntityType.ACADEMIC_LEVEL, CBTSyncOperation.CREATED)
    classroom = _mutation(CBTSyncEntityType.CLASS, CBTSyncOperation.CREATED)
    enrollment = _mutation(CBTSyncEntityType.STUDENT_ENROLLMENT, CBTSyncOperation.CREATED)
    assignment = _mutation(CBTSyncEntityType.TEACHER_ASSIGNMENT, CBTSyncOperation.CREATED)

    ordered = sorted(
        [assignment, enrollment, classroom, level, term, session],
        key=model_events._mutation_sort_key,
    )

    assert [item.entity_type for item in ordered] == [
        CBTSyncEntityType.ACADEMIC_SESSION,
        CBTSyncEntityType.ACADEMIC_TERM,
        CBTSyncEntityType.ACADEMIC_LEVEL,
        CBTSyncEntityType.CLASS,
        CBTSyncEntityType.STUDENT_ENROLLMENT,
        CBTSyncEntityType.TEACHER_ASSIGNMENT,
    ]
