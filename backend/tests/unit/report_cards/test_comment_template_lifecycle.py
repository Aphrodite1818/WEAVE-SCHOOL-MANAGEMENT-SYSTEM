from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.report_cards.comment_models import CommentTemplateOwnerType, CommentTemplateStatus
from app.modules.report_cards.comment_schemas import CommentTemplateCreate
from app.modules.report_cards.comment_service import ReportCommentService


class ScalarResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self.values


def _row(minimum: str, maximum: str):
    return SimpleNamespace(
        id=uuid4(),
        minimum_score=Decimal(minimum),
        maximum_score=Decimal(maximum),
        status=CommentTemplateStatus.ACTIVE,
    )


def test_comment_create_contract_is_performance_range_native() -> None:
    payload = CommentTemplateCreate(
        text="Good progress. Keep working consistently.",
        minimum_score=Decimal("60"),
        maximum_score=Decimal("70"),
        is_default=True,
    )

    assert payload.minimum_score == Decimal("60")
    assert payload.maximum_score == Decimal("70")
    assert not hasattr(payload, "grading_scale_id")
    assert not hasattr(payload, "grading_scale_ids")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        ("65", "70"),
        ("65", "75"),
        ("50", "65"),
        ("70", "80"),
    ],
)
async def test_distinct_inclusive_overlaps_are_rejected(minimum: str, maximum: str) -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult([_row("60", "70")])))

    with pytest.raises(ConflictException, match="overlaps"):
        await ReportCommentService._validate_non_overlapping_range(
            db,
            tenant_id=uuid4(),
            owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
            owner_id=uuid4(),
            minimum_score=Decimal(minimum),
            maximum_score=Decimal(maximum),
        )


@pytest.mark.asyncio
async def test_exact_same_range_is_allowed_for_multiple_wording_choices() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult([_row("60", "70")])))

    await ReportCommentService._validate_non_overlapping_range(
        db,
        tenant_id=uuid4(),
        owner_type=CommentTemplateOwnerType.TEACHER,
        owner_id=uuid4(),
        minimum_score=Decimal("60"),
        maximum_score=Decimal("70"),
    )


@pytest.mark.asyncio
async def test_adjacent_non_overlapping_decimal_ranges_are_allowed() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult([_row("60", "70")])))

    await ReportCommentService._validate_non_overlapping_range(
        db,
        tenant_id=uuid4(),
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=uuid4(),
        minimum_score=Decimal("70.01"),
        maximum_score=Decimal("80"),
    )
