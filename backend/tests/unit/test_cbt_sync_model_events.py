from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from app.modules.cbt.sync import model_events
from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
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

    def is_modified(self, _obj: object, *, include_collections: bool = False) -> bool:
        return True

    def get_nested_transaction(self):
        return self.nested_transaction

    def in_nested_transaction(self) -> bool:
        return self.nested_transaction is not None


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


def test_invisible_lifecycle_updates_become_explicit_deletes() -> None:
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
