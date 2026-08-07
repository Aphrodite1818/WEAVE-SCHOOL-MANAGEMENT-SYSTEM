from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException
from app.modules.student_academics.models import GradingScale
from app.modules.student_academics.schemas import GradingScaleUpdate
from app.modules.student_academics.service import StudentAcademicService


def _scale(tenant_id: uuid.UUID) -> GradingScale:
    return GradingScale(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        min_score=Decimal("70"),
        max_score=Decimal("100"),
        grade="A",
        remark="Excellent",
        is_active=False,
    )


@pytest.mark.asyncio
async def test_update_grading_scale_ignores_null_scores_before_comparison() -> None:
    tenant_id = uuid.uuid4()
    scale = _scale(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_grading_scale_by_id",
            new=AsyncMock(return_value=scale),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_grading_scales",
            new=AsyncMock(return_value=([], 0)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_grading_scale",
            new=AsyncMock(return_value=scale),
        ),
    ):
        updated = await StudentAcademicService.update_grading_scale(
            db=db,
            tenant_id=tenant_id,
            scale_id=scale.id,
            payload=GradingScaleUpdate(min_score=None, max_score=None, grade=None),
        )

    assert updated is scale
    assert scale.min_score == Decimal("70")
    assert scale.max_score == Decimal("100")
    assert scale.grade == "A"


@pytest.mark.asyncio
async def test_update_grading_scale_applies_explicit_scores() -> None:
    tenant_id = uuid.uuid4()
    scale = _scale(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_grading_scale_by_id",
            new=AsyncMock(return_value=scale),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_grading_scales",
            new=AsyncMock(return_value=([], 0)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_grading_scale",
            new=AsyncMock(return_value=scale),
        ),
    ):
        updated = await StudentAcademicService.update_grading_scale(
            db=db,
            tenant_id=tenant_id,
            scale_id=scale.id,
            payload=GradingScaleUpdate(
                min_score=Decimal("75"), max_score=Decimal("95")
            ),
        )

    assert updated.min_score == Decimal("75")
    assert updated.max_score == Decimal("95")


@pytest.mark.asyncio
async def test_update_grading_scale_rejects_invalid_effective_range() -> None:
    tenant_id = uuid.uuid4()
    scale = _scale(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_grading_scale_by_id",
        new=AsyncMock(return_value=scale),
    ):
        with pytest.raises(BadRequestException):
            await StudentAcademicService.update_grading_scale(
                db=db,
                tenant_id=tenant_id,
                scale_id=scale.id,
                payload=GradingScaleUpdate(
                    min_score=Decimal("95"), max_score=Decimal("90")
                ),
            )
