from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import AcademicTermName, AcademicTermStatus


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED])
async def test_class_specialization_is_immutable_once_term_closing_begins(status) -> None:
    db = AsyncMock()
    classroom = SimpleNamespace(id=uuid4(), academic_level_id=uuid4())
    term = SimpleNamespace(id=uuid4(), status=status)

    with pytest.raises(ConflictException, match="after term closing begins"):
        await AcademicCurriculumService._ensure_class_department_change_mutable(
            db,
            tenant_id=uuid4(),
            classroom=classroom,
            term=term,
            old_department_id=uuid4(),
            new_department_id=uuid4(),
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_term_department_change_checks_only_changed_specialized_subjects(
    monkeypatch,
) -> None:
    old_only = uuid4()
    shared = uuid4()
    new_only = uuid4()
    specialized = AsyncMock(side_effect=[{old_only, shared}, {shared, new_only}])
    dependencies = AsyncMock(return_value={"results": 0, "teacher_assignments": 0})
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_specialized_offering_subject_ids",
        specialized,
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_class_department_change_dependencies",
        dependencies,
    )
    classroom = SimpleNamespace(id=uuid4(), academic_level_id=uuid4())
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    affected = await AcademicCurriculumService._ensure_class_department_change_mutable(
        AsyncMock(),
        tenant_id=uuid4(),
        classroom=classroom,
        term=term,
        old_department_id=uuid4(),
        new_department_id=uuid4(),
    )

    assert affected == {old_only, new_only}
    assert dependencies.await_args.kwargs["affected_curriculum_subject_ids"] == {
        old_only,
        new_only,
    }


@pytest.mark.asyncio
async def test_general_subject_activity_does_not_block_department_correction(monkeypatch) -> None:
    specialized = AsyncMock(side_effect=[set(), set()])
    dependencies = AsyncMock(return_value={"results": 0, "teacher_assignments": 0})
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_specialized_offering_subject_ids",
        specialized,
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_class_department_change_dependencies",
        dependencies,
    )
    classroom = SimpleNamespace(id=uuid4(), academic_level_id=uuid4())
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    affected = await AcademicCurriculumService._ensure_class_department_change_mutable(
        AsyncMock(),
        tenant_id=uuid4(),
        classroom=classroom,
        term=term,
        old_department_id=uuid4(),
        new_department_id=uuid4(),
    )

    assert affected == set()
    dependencies.assert_awaited_once()
    assert dependencies.await_args.kwargs["affected_curriculum_subject_ids"] == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependencies",
    [
        {"results": 1, "teacher_assignments": 0},
        {"results": 0, "teacher_assignments": 1},
        {"results": 2, "teacher_assignments": 3},
    ],
)
async def test_open_term_department_change_blocks_used_specialized_subjects(
    monkeypatch,
    dependencies,
) -> None:
    affected_subject = uuid4()
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_specialized_offering_subject_ids",
        AsyncMock(side_effect=[{affected_subject}, set()]),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_class_department_change_dependencies",
        AsyncMock(return_value=dependencies),
    )
    classroom = SimpleNamespace(id=uuid4(), academic_level_id=uuid4())
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    with pytest.raises(ConflictException, match="already in operational use"):
        await AcademicCurriculumService._ensure_class_department_change_mutable(
            AsyncMock(),
            tenant_id=uuid4(),
            classroom=classroom,
            term=term,
            old_department_id=uuid4(),
            new_department_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_department_change_dependencies_scope_results_and_teacher_assignments() -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    subject_ids = {uuid4(), uuid4()}
    term = SimpleNamespace(
        id=uuid4(),
        start_date=date(2026, 1, 5),
        end_date=date(2026, 4, 10),
    )
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[ScalarResult(2), ScalarResult(1)])
    )

    counts = await AcademicCurriculumService._class_department_change_dependencies(
        db,
        tenant_id=tenant_id,
        class_id=class_id,
        term=term,
        affected_curriculum_subject_ids=subject_ids,
    )

    assert counts == {"results": 2, "teacher_assignments": 1}
    result_statement = str(db.execute.await_args_list[0].args[0])
    assignment_statement = str(db.execute.await_args_list[1].args[0])
    assert "student_subject_results.class_id" in result_statement
    assert "student_subject_results.academic_term_id" in result_statement
    assert "curriculum_subject_id" in result_statement
    assert "teacher_assignments.class_id" in assignment_statement
    assert "effective_from" in assignment_statement
    assert "effective_to" in assignment_statement


def test_specialization_requirement_starts_at_configured_term_position() -> None:
    level = SimpleNamespace(specialization_required_from_term_position=2)

    assert (
        AcademicCurriculumService._specialization_required_for_term(
            level,
            SimpleNamespace(name=AcademicTermName.FIRST_TERM),
        )
        is False
    )
    assert (
        AcademicCurriculumService._specialization_required_for_term(
            level,
            SimpleNamespace(name=AcademicTermName.SECOND_TERM),
        )
        is True
    )
    assert (
        AcademicCurriculumService._specialization_required_for_term(
            level,
            SimpleNamespace(name=AcademicTermName.THIRD_TERM),
        )
        is True
    )


@pytest.mark.asyncio
async def test_clear_required_open_term_specialization_is_rejected(monkeypatch) -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    term_id = uuid4()
    department_id = uuid4()
    assignment = SimpleNamespace(id=uuid4(), department_id=department_id)
    classroom = SimpleNamespace(id=class_id, academic_level_id=uuid4())
    level = SimpleNamespace(specialization_required_from_term_position=2)
    term = SimpleNamespace(
        id=term_id,
        name=AcademicTermName.SECOND_TERM,
        status=AcademicTermStatus.OPEN,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = assignment
    db = SimpleNamespace(execute=AsyncMock(return_value=result), delete=AsyncMock())

    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_term",
        AsyncMock(return_value=term),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_ensure_department_capability",
        AsyncMock(return_value=level),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_ensure_class_department_change_mutable",
        AsyncMock(return_value=set()),
    )

    with pytest.raises(ConflictException, match="requires department specialization"):
        await AcademicCurriculumService.clear_class_department(
            db,
            tenant_id,
            class_id,
            term_id,
            uuid4(),
        )

    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_required_draft_term_specialization_can_be_cleared(monkeypatch) -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    term_id = uuid4()
    assignment = SimpleNamespace(id=uuid4(), department_id=uuid4())
    classroom = SimpleNamespace(id=class_id, academic_level_id=uuid4())
    level = SimpleNamespace(specialization_required_from_term_position=2)
    term = SimpleNamespace(
        id=term_id,
        name=AcademicTermName.SECOND_TERM,
        status=AcademicTermStatus.DRAFT,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = assignment
    db = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )

    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_term",
        AsyncMock(return_value=term),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_ensure_department_capability",
        AsyncMock(return_value=level),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_ensure_class_department_change_mutable",
        AsyncMock(return_value=set()),
    )

    await AcademicCurriculumService.clear_class_department(
        db,
        tenant_id,
        class_id,
        term_id,
        uuid4(),
    )

    db.delete.assert_awaited_once_with(assignment)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_class_department_checks_write_guard_before_loading_term(monkeypatch) -> None:
    guard = AsyncMock()
    term = AsyncMock(side_effect=RuntimeError("stop after guard"))
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        guard,
    )
    monkeypatch.setattr(AcademicCurriculumService, "_term", term)
    tenant_id = uuid4()
    db = AsyncMock()

    with pytest.raises(RuntimeError, match="stop after guard"):
        await AcademicCurriculumService.set_class_department(
            db,
            tenant_id,
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
        )

    guard.assert_awaited_once_with(db, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_clear_class_department_checks_write_guard_before_loading_term(monkeypatch) -> None:
    guard = AsyncMock()
    term = AsyncMock(side_effect=RuntimeError("stop after guard"))
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        guard,
    )
    monkeypatch.setattr(AcademicCurriculumService, "_term", term)
    tenant_id = uuid4()
    db = AsyncMock()

    with pytest.raises(RuntimeError, match="stop after guard"):
        await AcademicCurriculumService.clear_class_department(
            db,
            tenant_id,
            uuid4(),
            uuid4(),
            uuid4(),
        )

    guard.assert_awaited_once_with(db, tenant_id=tenant_id)


def test_open_term_specialization_audit_records_old_and_new_scope() -> None:
    db = MagicMock()
    assignment_id = uuid4()
    class_id = uuid4()
    term_id = uuid4()
    old_department_id = uuid4()
    new_department_id = uuid4()
    affected = {uuid4(), uuid4()}

    AcademicCurriculumService._record_open_term_specialization_audit(
        db,
        tenant_id=uuid4(),
        assignment_id=assignment_id,
        class_id=class_id,
        term_id=term_id,
        old_department_id=old_department_id,
        new_department_id=new_department_id,
        admin_id=uuid4(),
        affected_subject_ids=affected,
    )

    audit = db.add.call_args.args[0]
    assert audit.entity_type == "specialization"
    assert audit.entity_id == assignment_id
    assert audit.action == "department_changed"
    assert audit.metadata_json["class_id"] == str(class_id)
    assert audit.metadata_json["academic_term_id"] == str(term_id)
    assert audit.metadata_json["previous_department_id"] == str(old_department_id)
    assert audit.metadata_json["new_department_id"] == str(new_department_id)
    assert set(audit.metadata_json["affected_curriculum_subject_ids"]) == {
        str(value) for value in affected
    }
