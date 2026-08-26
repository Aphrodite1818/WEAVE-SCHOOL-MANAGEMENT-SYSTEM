from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_v2_schemas import CurriculumOfferingCreate
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import AcademicTermStatus


class ScalarResult:
    def __init__(self, value: int):
        self.value = value

    def scalar_one(self):
        return self.value


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED])
async def test_offering_changes_are_immutable_once_term_closing_begins(status) -> None:
    db = AsyncMock()
    term = SimpleNamespace(id=uuid4(), status=status)

    with pytest.raises(ConflictException, match="cannot be changed after term closing begins"):
        await AcademicCurriculumService._ensure_offering_change_mutable(
            db,
            tenant_id=uuid4(),
            term=term,
            curriculum_subject_id=uuid4(),
            department_id=None,
            removing=False,
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_draft_term_offering_removal_is_freely_configurable(monkeypatch) -> None:
    dependencies = AsyncMock()
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_offering_open_term_dependencies",
        dependencies,
    )
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.DRAFT)

    await AcademicCurriculumService._ensure_offering_change_mutable(
        AsyncMock(),
        tenant_id=uuid4(),
        term=term,
        curriculum_subject_id=uuid4(),
        department_id=None,
        removing=True,
    )

    dependencies.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_term_can_add_an_offering_without_dependency_freeze(monkeypatch) -> None:
    dependencies = AsyncMock()
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_offering_open_term_dependencies",
        dependencies,
    )
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    await AcademicCurriculumService._ensure_offering_change_mutable(
        AsyncMock(),
        tenant_id=uuid4(),
        term=term,
        curriculum_subject_id=uuid4(),
        department_id=uuid4(),
        removing=False,
    )

    dependencies.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_term_unused_offering_can_be_removed(monkeypatch) -> None:
    dependencies = AsyncMock(return_value={"results": 0, "teacher_assignments": 0})
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_offering_open_term_dependencies",
        dependencies,
    )
    tenant_id = uuid4()
    curriculum_subject_id = uuid4()
    department_id = uuid4()
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    await AcademicCurriculumService._ensure_offering_change_mutable(
        AsyncMock(),
        tenant_id=tenant_id,
        term=term,
        curriculum_subject_id=curriculum_subject_id,
        department_id=department_id,
        removing=True,
    )

    dependencies.assert_awaited_once()
    kwargs = dependencies.await_args.kwargs
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["curriculum_subject_id"] == curriculum_subject_id
    assert kwargs["department_id"] == department_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependencies",
    [
        {"results": 1, "teacher_assignments": 0},
        {"results": 0, "teacher_assignments": 1},
        {"results": 2, "teacher_assignments": 3},
    ],
)
async def test_open_term_used_offering_cannot_be_removed(monkeypatch, dependencies) -> None:
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_offering_open_term_dependencies",
        AsyncMock(return_value=dependencies),
    )
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    with pytest.raises(ConflictException, match="already in operational use"):
        await AcademicCurriculumService._ensure_offering_change_mutable(
            AsyncMock(),
            tenant_id=uuid4(),
            term=term,
            curriculum_subject_id=uuid4(),
            department_id=None,
            removing=True,
        )


@pytest.mark.asyncio
async def test_department_offering_dependencies_are_scoped_to_term_department() -> None:
    tenant_id = uuid4()
    department_id = uuid4()
    term = SimpleNamespace(
        id=uuid4(),
        status=AcademicTermStatus.OPEN,
        start_date=date(2026, 1, 5),
        end_date=date(2026, 4, 10),
    )
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[ScalarResult(2), ScalarResult(1)])
    )

    counts = await AcademicCurriculumService._offering_open_term_dependencies(
        db,
        tenant_id=tenant_id,
        term=term,
        curriculum_subject_id=uuid4(),
        department_id=department_id,
    )

    assert counts == {"results": 2, "teacher_assignments": 1}
    result_statement = str(db.execute.await_args_list[0].args[0])
    assignment_statement = str(db.execute.await_args_list[1].args[0])
    assert "class_term_department_assignments" in result_statement
    assert "class_term_department_assignments" in assignment_statement
    assert "department_id" in result_statement
    assert "effective_from" in assignment_statement
    assert "effective_to" in assignment_statement


@pytest.mark.asyncio
async def test_add_offering_checks_academic_write_guard_before_loading_context(monkeypatch) -> None:
    guard = AsyncMock()
    context = AsyncMock(side_effect=RuntimeError("stop after guard"))
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        guard,
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_curriculum_subject_context",
        context,
    )
    tenant_id = uuid4()

    with pytest.raises(RuntimeError, match="stop after guard"):
        await AcademicCurriculumService.add_offering(
            AsyncMock(),
            tenant_id,
            uuid4(),
            CurriculumOfferingCreate(academic_term_id=uuid4()),
        )

    guard.assert_awaited_once_with(AsyncMock.ANY if False else guard.await_args.args[0] if guard.await_args.args else None)
