"""Persistence invariants between curriculum semantics and student elective choices.

A student's selected curriculum-subject identity must never outlive or contradict
that subject's elective-group semantics. Service-layer checks provide good UX, but
this boundary guard protects imports, future services, and direct ORM write paths
from creating stale selections or leaking raw FK failures.
"""

from __future__ import annotations

from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_models import (
    CurriculumSubject,
    StudentElectiveSelection,
)


def _selection_dependency_count(
    session: Session,
    *,
    tenant_id,
    curriculum_subject_id,
) -> int:
    persisted = int(
        session.execute(
            select(func.count(StudentElectiveSelection.id)).where(
                StudentElectiveSelection.tenant_id == tenant_id,
                StudentElectiveSelection.curriculum_subject_id == curriculum_subject_id,
            )
        ).scalar_one()
    )

    # before_flush queries still see rows scheduled for deletion in the database,
    # while pending inserts are not visible yet. Reconcile both sets so this guard
    # reflects the transaction's intended final dependency count.
    deleted = sum(
        1
        for row in session.deleted
        if isinstance(row, StudentElectiveSelection)
        and row.tenant_id == tenant_id
        and row.curriculum_subject_id == curriculum_subject_id
    )
    pending = sum(
        1
        for row in session.new
        if isinstance(row, StudentElectiveSelection)
        and row.tenant_id == tenant_id
        and row.curriculum_subject_id == curriculum_subject_id
    )
    return max(0, persisted - deleted + pending)


def _semantic_change(row: CurriculumSubject) -> bool:
    state = inspect(row)
    return (
        state.attrs.is_elective.history.has_changes()
        or state.attrs.elective_group_id.history.has_changes()
    )


@event.listens_for(Session, "before_flush")
def enforce_elective_selection_integrity(
    session: Session,
    _flush_context,
    _instances,
) -> None:
    """Block semantic rewrites/deletes while student selections depend on a subject."""

    candidates = {
        row
        for row in list(session.dirty) + list(session.deleted)
        if isinstance(row, CurriculumSubject)
    }
    for row in candidates:
        deleting = row in session.deleted
        if not deleting and not _semantic_change(row):
            continue

        count = _selection_dependency_count(
            session,
            tenant_id=row.tenant_id,
            curriculum_subject_id=row.id,
        )
        if count <= 0:
            continue

        if deleting:
            message = (
                "This curriculum subject has student elective selections and cannot be "
                "permanently deleted. Remove or replace those selections first."
            )
        else:
            message = (
                "Elective settings cannot change while students have selected this "
                "curriculum subject. Clear those selections before changing its group "
                "or compulsory/elective meaning."
            )
        raise ConflictException(
            message,
            payload={"dependency_counts": {"student_elective_selections": count}},
        )
