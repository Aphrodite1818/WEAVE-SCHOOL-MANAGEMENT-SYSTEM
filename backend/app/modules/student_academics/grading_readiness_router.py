"""Canonical grading-scale readiness endpoint."""

from decimal import Decimal
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import GradingScaleReadiness
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/grading-scales",
    tags=["Tenant Admin Academics"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]


@router.get(
    "/readiness-preview",
    response_model=GradingScaleReadiness,
)
async def preview_grading_scale_readiness(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GradingScaleReadiness:
    scales, _ = await StudentAcademicRepository.list_grading_scales(
        db,
        current_admin.tenant_id,
        limit=1000,
        active_only=True,
    )
    if not scales:
        return GradingScaleReadiness(
            is_ready=False,
            missing_coverage=["0-100"],
            overlaps=[],
            messages=["No active grading scales found."],
        )

    ordered = sorted(scales, key=lambda item: (item.min_score, item.max_score))
    missing: list[str] = []
    overlaps: list[str] = []

    first = ordered[0]
    if first.min_score != Decimal("0"):
        missing.append(f"0-{first.min_score}")

    previous = first
    for current in ordered[1:]:
        # Scores are entered as points and the configured UI uses inclusive
        # whole-number bands such as 0-39 followed by 40-49. Those bands are
        # contiguous, not separated by a decimal-sized gap.
        expected_next = previous.max_score + Decimal("1")
        if current.min_score < expected_next:
            overlaps.append(f"{current.min_score}-{previous.max_score}")
        elif current.min_score > expected_next:
            missing.append(f"{expected_next}-{current.min_score - Decimal('1')}")
        if current.max_score > previous.max_score:
            previous = current

    if previous.max_score < Decimal("100"):
        missing.append(f"{previous.max_score + Decimal('1')}-100")
    elif previous.max_score > Decimal("100"):
        overlaps.append(f"100-{previous.max_score}")

    ready = not missing and not overlaps
    messages = (
        []
        if ready
        else [
            "Active grading scales must cover every whole-number score from 0 through 100 exactly once."
        ]
    )
    return GradingScaleReadiness(
        is_ready=ready,
        missing_coverage=missing,
        overlaps=overlaps,
        messages=messages,
    )
