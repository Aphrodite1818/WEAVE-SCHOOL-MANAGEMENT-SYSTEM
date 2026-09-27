"""Persistence-boundary invariant for active grading-scale range overlap.

Inactive grading scales are intentionally allowed to overlap so administrators can
stage a replacement before deactivating the old scale. The invariant applies only
to ranges that are simultaneously active, matching the established lifecycle API.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import GradingScale


def ranges_overlap(
    left_min: Decimal,
    left_max: Decimal,
    right_min: Decimal,
    right_max: Decimal,
) -> bool:
    """Return True when two inclusive score ranges share any score."""

    return left_min <= right_max and left_max >= right_min


def _changed_active_grading_scales(session: Session) -> list[GradingScale]:
    rows: list[GradingScale] = []
    for candidate in list(session.new) + list(session.dirty):
        if not isinstance(candidate, GradingScale) or candidate in session.deleted:
            continue
        if not candidate.is_active:
            continue
        if candidate in session.new or session.is_modified(candidate, include_collections=False):
            rows.append(candidate)
    return rows


@event.listens_for(Session, "before_flush")
def enforce_grading_scale_non_overlap(
    session: Session,
    _flush_context,
    _instances,
) -> None:
    """Reject overlap only among grading scales that are simultaneously active."""

    changed = _changed_active_grading_scales(session)
    if not changed:
        return

    # Catch two active overlapping writes in the same transaction before either
    # exists in the database.
    for index, left in enumerate(changed):
        for right in changed[index + 1 :]:
            if left.tenant_id != right.tenant_id or left.id == right.id:
                continue
            if ranges_overlap(left.min_score, left.max_score, right.min_score, right.max_score):
                raise ConflictException("Grading scale ranges cannot overlap.")

    # Compare changed active rows with persisted active rows. Inclusive boundaries
    # mean [0, 50] and [50, 60] overlap; adjacent ranges must share no endpoint.
    for row in changed:
        query = select(GradingScale).where(
            GradingScale.tenant_id == row.tenant_id,
            GradingScale.is_active.is_(True),
        )
        if row.id is not None:
            query = query.where(GradingScale.id != row.id)
        persisted = list(session.execute(query).scalars())
        for other in persisted:
            if other in session.deleted or not other.is_active:
                continue
            if ranges_overlap(row.min_score, row.max_score, other.min_score, other.max_score):
                raise ConflictException("Grading scale ranges cannot overlap.")
