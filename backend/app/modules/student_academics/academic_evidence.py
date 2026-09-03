"""Immutable academic evidence checks for curriculum reinterpretation operations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.modules.classes.models import ClassRoom
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.models import StudentSubjectResult


class AcademicEvidenceProtection:
    """Authoritative guard for persisted evidence whose meaning must not change.

    Teacher assignments are deliberately excluded: their temporal lifecycle is
    reconcilable. The cloud service currently stores no CBT exam attempts or CBT
    results, so synchronization delivery rows are not misclassified as evidence.
    """

    @staticmethod
    async def counts_for_class_term(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_term_id: uuid.UUID,
        affected_curriculum_subject_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, int]:
        result_query = select(func.count(StudentSubjectResult.id)).where(
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.class_id == class_id,
            StudentSubjectResult.academic_term_id == academic_term_id,
        )
        if affected_curriculum_subject_ids is not None:
            if affected_curriculum_subject_ids:
                result_query = result_query.where(
                    StudentSubjectResult.curriculum_subject_id.in_(affected_curriculum_subject_ids)
                )
            else:
                result_query = result_query.where(False)
        results = int((await db.execute(result_query)).scalar_one() or 0)
        report_cards = int(
            (
                await db.execute(
                    select(func.count(ReportCard.id)).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.class_id == class_id,
                        ReportCard.academic_term_id == academic_term_id,
                    )
                )
            ).scalar_one()
            or 0
        )
        return {"results": results, "report_cards": report_cards, "cbt": 0}

    @staticmethod
    async def counts_for_level_terms(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        academic_term_ids: set[uuid.UUID],
    ) -> dict[str, int]:
        if not academic_term_ids:
            return {"results": 0, "report_cards": 0, "cbt": 0}
        class_scope = select(ClassRoom.id).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.academic_level_id == academic_level_id,
        )
        results = int(
            (
                await db.execute(
                    select(func.count(StudentSubjectResult.id)).where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.class_id.in_(class_scope),
                        StudentSubjectResult.academic_term_id.in_(academic_term_ids),
                    )
                )
            ).scalar_one()
            or 0
        )
        report_cards = int(
            (
                await db.execute(
                    select(func.count(ReportCard.id)).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.class_id.in_(class_scope),
                        ReportCard.academic_term_id.in_(academic_term_ids),
                    )
                )
            ).scalar_one()
            or 0
        )
        return {"results": results, "report_cards": report_cards, "cbt": 0}

    @staticmethod
    def ensure_none(counts: dict[str, int], *, operation: str) -> None:
        blockers = {key: value for key, value in counts.items() if value > 0}
        if blockers:
            raise ConflictException(
                f"{operation} cannot continue because immutable academic evidence already exists.",
                payload={"dependency_counts": blockers},
            )
