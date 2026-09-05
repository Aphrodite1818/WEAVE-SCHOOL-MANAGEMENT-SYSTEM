"""Authoritative class ranking independent of report-generation order."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.models import ReportCard, ReportCardStatus
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.students.repository import StudentRepository


def _dense_rank(values: list[tuple[uuid.UUID, Decimal]]) -> dict[uuid.UUID, int]:
    ordered = sorted(values, key=lambda item: item[1], reverse=True)
    ranks: dict[uuid.UUID, int] = {}
    current_rank = 0
    previous_score: Decimal | None = None
    for student_id, score in ordered:
        if previous_score is None or score != previous_score:
            current_rank += 1
            previous_score = score
        ranks[student_id] = current_rank
    return ranks


async def refresh_draft_rank_from_authoritative_results(
    db: AsyncSession,
    *,
    card: ReportCard,
) -> ReportCard:
    """Set a draft's rank from every academically complete student in its class.

    A report card may be generated before classmates' cards. Ranking therefore
    cannot use generated report rows as the population. We derive the population
    from current class membership plus finalized/locked expected results. Published
    rows are never passed to this helper and remain immutable snapshots.
    """

    if card.status != ReportCardStatus.DRAFT:
        return card
    if card.class_id is None:
        raise BadRequestException("A resolved class is required for report ranking.")

    students, _ = await StudentRepository.list_for_tenant(
        db=db,
        tenant_id=card.tenant_id,
        class_id=card.class_id,
        limit=500,
    )
    score_rows: list[tuple[uuid.UUID, Decimal]] = []
    for student in students:
        ready, average, _ = await ReportCommentService._academic_readiness(
            db,
            tenant_id=card.tenant_id,
            student_id=student.id,
            academic_session_id=card.academic_session_id,
            academic_term_id=card.academic_term_id,
        )
        if ready and average is not None:
            score_rows.append((student.id, average))

    ranks = _dense_rank(score_rows)
    if card.student_id not in ranks:
        raise BadRequestException(
            "The student's authoritative class ranking could not be resolved from locked results."
        )
    card.position = ranks[card.student_id]
    card.position_out_of = len(score_rows)
    return await ReportCardRepository.save(db, card)
