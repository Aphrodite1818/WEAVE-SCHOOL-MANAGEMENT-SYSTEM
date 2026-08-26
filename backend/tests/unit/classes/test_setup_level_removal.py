from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import AcademicLevelStatus
from app.modules.classes.service import AcademicLevelService


@pytest.mark.asyncio
async def test_setup_level_removal_rejects_a_level_with_class_arms() -> None:
    tenant_id, level_id = uuid4(), uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    level = SimpleNamespace(id=level_id, status=AcademicLevelStatus.DRAFT)
    db = MagicMock()

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.count_setup_dependencies",
            new=AsyncMock(
                return_value={
                    "classes_total": 1,
                    "departments_total": 0,
                    "curriculum_subjects_total": 0,
                    "enrollments_total": 0,
                }
            ),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.delete",
            new=AsyncMock(),
        ) as delete_level,
    ):
        with pytest.raises(ConflictException, match="already referenced"):
            await AcademicLevelService.purge_setup_level(db, actor, level_id)

    delete_level.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_level_removal_deletes_an_unreferenced_armless_level() -> None:
    tenant_id, level_id = uuid4(), uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    level = SimpleNamespace(id=level_id, status=AcademicLevelStatus.DRAFT)
    response = MagicMock()
    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.count_setup_dependencies",
            new=AsyncMock(
                return_value={
                    "classes_total": 0,
                    "departments_total": 0,
                    "curriculum_subjects_total": 0,
                    "enrollments_total": 0,
                }
            ),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.delete",
            new=AsyncMock(),
        ) as delete_level,
        patch(
            "app.modules.classes.service.AcademicLevelResponse.model_validate",
            return_value=response,
        ),
    ):
        result = await AcademicLevelService.purge_setup_level(db, actor, level_id)

    assert result is response
    delete_level.assert_awaited_once_with(db, level)
    db.commit.assert_awaited_once()
