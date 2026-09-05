"""Helpers for checking immutable academic evidence on enrollment segments."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models import StudentAttendanceRecord, StudentAttendanceSheet
from app.modules.student_academics.models import AcademicTerm, StudentSubjectResult


class StudentEnrollmentEvidenceService:
    """Count evidence that would make a backdated enrollment boundary unsafe."""

    @staticmethod
    async def segment_dependency_counts(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        enrollment_id: UUID,
        on_or_after: date | None = None,
    ) -> dict[str, int]:
        attendance_filters = [
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.student_enrollment_id == enrollment_id,
        ]
        if on_or_after is not None:
            attendance_filters.append(StudentAttendanceSheet.attendance_date >= on_or_after)
        attendance_query = (
            select(func.count())
            .select_from(StudentAttendanceRecord)
            .join(
                StudentAttendanceSheet,
                StudentAttendanceSheet.id == StudentAttendanceRecord.sheet_id,
            )
            .where(*attendance_filters)
        )

        result_filters = [
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.student_enrollment_id == enrollment_id,
        ]
        result_query = select(func.count()).select_from(StudentSubjectResult).where(*result_filters)
        if on_or_after is not None:
            result_query = result_query.join(
                AcademicTerm,
                AcademicTerm.id == StudentSubjectResult.academic_term_id,
            ).where(
                AcademicTerm.tenant_id == tenant_id,
                (AcademicTerm.end_date.is_(None) | (AcademicTerm.end_date >= on_or_after)),
            )

        attendance = int((await db.execute(attendance_query)).scalar_one() or 0)
        results = int((await db.execute(result_query)).scalar_one() or 0)
        return {"attendance": attendance, "results": results}
