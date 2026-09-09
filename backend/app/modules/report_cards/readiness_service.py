"""Canonical report-result readiness derivation.

This module owns the expensive curriculum/result/component calculation shared by
admin readiness and class-teacher comment workflows. Redis caches only derived
read state; database rows remain authoritative.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.report_cards.cache import ReportReadinessCache
from app.modules.report_cards.performance_service import resolve_report_performance
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.models import AcademicResultStatus, GradingScale
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.subjects.repository import SubjectRepository


@dataclass(frozen=True, slots=True)
class StudentResultReadiness:
    expected_count: int
    locked_count: int
    missing_subject_names: tuple[str, ...]
    performance_percentage: Decimal | None
    grading_scale_id: uuid.UUID | None
    overall_grade: str | None

    @property
    def complete(self) -> bool:
        return self.expected_count > 0 and self.locked_count == self.expected_count


class ReportReadinessService:
    @staticmethod
    async def resolve_result_readiness(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> StudentResultReadiness:
        cached = await ReportReadinessCache.get(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        if cached is not None:
            percentage_raw = cached.get("performance_percentage")
            scale_raw = cached.get("grading_scale_id")
            return StudentResultReadiness(
                expected_count=int(cached.get("expected_count") or 0),
                locked_count=int(cached.get("locked_count") or 0),
                missing_subject_names=tuple(cached.get("missing_subject_names") or []),
                performance_percentage=(
                    Decimal(str(percentage_raw)) if percentage_raw is not None else None
                ),
                grading_scale_id=(uuid.UUID(str(scale_raw)) if scale_raw else None),
                overall_grade=(str(cached.get("overall_grade")) if cached.get("overall_grade") else None),
            )

        expected = await CurriculumResolutionService.resolve_student_curriculum(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        if not expected:
            snapshot = StudentResultReadiness(
                expected_count=0,
                locked_count=0,
                missing_subject_names=(),
                performance_percentage=None,
                grading_scale_id=None,
                overall_grade=None,
            )
            await ReportReadinessService._cache_snapshot(
                snapshot,
                tenant_id=tenant_id,
                student_id=student_id,
                academic_session_id=academic_session_id,
                academic_term_id=academic_term_id,
            )
            return snapshot

        results, _ = await StudentAcademicRepository.list_results(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            finalized_only=True,
            limit=500,
        )
        by_curriculum = {item.curriculum_subject_id: item for item in results}
        locked_results = []
        missing_subject_names: list[str] = []
        for item in expected:
            result = by_curriculum.get(item.curriculum_subject_id)
            if result is None or result.status != AcademicResultStatus.LOCKED:
                subject = await SubjectRepository.get_subject_by_id(db, tenant_id, item.subject_id)
                missing_subject_names.append(subject.name if subject else str(item.subject_id))
                continue
            locked_results.append(result)

        percentage: Decimal | None = None
        scale: GradingScale | None = None
        if len(locked_results) == len(expected):
            performance = await resolve_report_performance(
                db,
                tenant_id=tenant_id,
                results=locked_results,
            )
            if performance is not None:
                percentage = performance.percentage
                scale = await StudentAcademicRepository.find_grade_for_score(
                    db=db,
                    tenant_id=tenant_id,
                    score=percentage,
                )

        snapshot = StudentResultReadiness(
            expected_count=len(expected),
            locked_count=len(locked_results),
            missing_subject_names=tuple(missing_subject_names),
            performance_percentage=percentage,
            grading_scale_id=scale.id if scale is not None else None,
            overall_grade=scale.grade if scale is not None else None,
        )
        await ReportReadinessService._cache_snapshot(
            snapshot,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        return snapshot

    @staticmethod
    async def grading_scale_for_snapshot(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        snapshot: StudentResultReadiness,
    ) -> GradingScale | None:
        if snapshot.grading_scale_id is None:
            return None
        return await StudentAcademicRepository.get_grading_scale_by_id(
            db,
            tenant_id,
            snapshot.grading_scale_id,
        )

    @staticmethod
    async def _cache_snapshot(
        snapshot: StudentResultReadiness,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        await ReportReadinessCache.set(
            {
                "expected_count": snapshot.expected_count,
                "locked_count": snapshot.locked_count,
                "missing_subject_names": list(snapshot.missing_subject_names),
                "performance_percentage": (
                    str(snapshot.performance_percentage)
                    if snapshot.performance_percentage is not None
                    else None
                ),
                "grading_scale_id": (
                    str(snapshot.grading_scale_id) if snapshot.grading_scale_id is not None else None
                ),
                "overall_grade": snapshot.overall_grade,
            },
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
