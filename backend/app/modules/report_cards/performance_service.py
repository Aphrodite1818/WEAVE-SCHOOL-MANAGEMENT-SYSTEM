"""Canonical report-scope performance aggregation.

All report/comment workflows must derive the student's overall percentage from
this module so manual results, CBT-ingested results, readiness and generated
report cards cannot drift apart.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.models import StudentSubjectResult
from app.modules.student_academics.repository import StudentAcademicRepository


PERCENT_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class ReportPerformance:
    earned_score: Decimal
    possible_score: Decimal
    percentage: Decimal
    subject_count: int


def calculate_report_performance(
    results: list[StudentSubjectResult],
    component_scores_by_result: dict[uuid.UUID, list[tuple[object, object]]],
) -> ReportPerformance | None:
    """Return a weighted percentage for one report scope.

    The denominator is the sum of configured assessment-component maximums for
    every included subject. This intentionally does *not* average subject
    percentages: a 50-mark subject and a 100-mark subject contribute according
    to their actual possible marks.
    """

    if not results:
        return None

    earned = Decimal("0")
    possible = Decimal("0")

    for result in results:
        components = component_scores_by_result.get(result.id) or []
        if not components:
            return None

        # Defensive de-duplication keeps a malformed joined result from
        # inflating the denominator without hiding a missing component set.
        seen_component_ids: set[object] = set()
        result_possible = Decimal("0")
        for component, _score in components:
            component_id = getattr(component, "id", None)
            marker = component_id if component_id is not None else id(component)
            if marker in seen_component_ids:
                continue
            seen_component_ids.add(marker)
            maximum = Decimal(str(getattr(component, "maximum_score", "0")))
            if maximum <= 0:
                return None
            result_possible += maximum

        if result_possible <= 0:
            return None
        earned += Decimal(str(result.total_score))
        possible += result_possible

    if possible <= 0:
        return None

    percentage = ((earned / possible) * HUNDRED).quantize(
        PERCENT_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    return ReportPerformance(
        earned_score=earned.quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP),
        possible_score=possible.quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP),
        percentage=percentage,
        subject_count=len(results),
    )


async def resolve_report_performance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    results: list[StudentSubjectResult],
) -> ReportPerformance | None:
    if not results:
        return None
    component_scores = await StudentAcademicRepository.list_result_component_scores_batch(
        db,
        tenant_id,
        results,
    )
    return calculate_report_performance(results, component_scores)
