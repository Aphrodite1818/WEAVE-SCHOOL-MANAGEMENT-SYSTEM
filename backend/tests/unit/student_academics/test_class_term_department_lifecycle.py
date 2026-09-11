from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import AcademicTermName, AcademicTermStatus


def test_specialization_requirement_uses_configured_term_position() -> None:
    level = SimpleNamespace(specialization_required_from_term_position=2)
    assert not CurriculumResolutionService.specialization_is_active(
        level, SimpleNamespace(name=AcademicTermName.FIRST_TERM)
    )
    assert CurriculumResolutionService.specialization_is_active(
        level, SimpleNamespace(name=AcademicTermName.SECOND_TERM)
    )
    assert CurriculumResolutionService.specialization_is_active(
        level, SimpleNamespace(name=AcademicTermName.THIRD_TERM)
    )


@pytest.mark.asyncio
async def test_required_term_specialization_cannot_be_cleared(monkeypatch) -> None:
    tenant_id, class_id, term_id = uuid4(), uuid4(), uuid4()
    assignment = SimpleNamespace(id=uuid4(), academic_level_department_id=uuid4())
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
    monkeypatch.setattr(AcademicCurriculumService, "_term", AsyncMock(return_value=term))
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        AcademicCurriculumService,
        "_ensure_department_capability",
        AsyncMock(return_value=level),
    )

    with pytest.raises(ConflictException, match="requires specialization"):
        await AcademicCurriculumService.clear_class_department(
            db, tenant_id, class_id, term_id, uuid4()
        )

    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_class_department_checks_write_guard_first(monkeypatch) -> None:
    guard = AsyncMock()
    term = AsyncMock(side_effect=RuntimeError("stop after guard"))
    monkeypatch.setattr(
        "app.modules.student_academics.curriculum_v2_service.ensure_academic_write_window",
        guard,
    )
    monkeypatch.setattr(AcademicCurriculumService, "_term", term)
    tenant_id = uuid4()

    with pytest.raises(RuntimeError, match="stop after guard"):
        await AcademicCurriculumService.set_class_department(
            AsyncMock(), tenant_id, uuid4(), uuid4(), uuid4(), uuid4()
        )

    guard.assert_awaited_once()
