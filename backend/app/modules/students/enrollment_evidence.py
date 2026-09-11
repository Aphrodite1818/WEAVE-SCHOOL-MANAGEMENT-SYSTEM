"""Helpers for checking immutable academic evidence on enrollment segments."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models import StudentAttendanceRecord, StudentAttendanceSheet
from app.modules.cbt.results.models import CBTResultIngestionItem
from app.modules.report_cards.comment_models import StudentTermTeacherComment
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.models import (
    AcademicTerm,
    StudentProgressionItem,
    StudentSubjectResult,
)
from app.modules.students.models import StudentEnrollment


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
        enrollment = (
            await db.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.id == enrollment_id,
                )
            )
        ).scalar_one_or_none()
        if enrollment is None:
            return {
                "attendance": 0,
                "results": 0,
                "teacher_comments": 0,
                "report_cards": 0,
                "cbt_results": 0,
                "progression": 0,
            }
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
        comments = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentTermTeacherComment)
                    .where(
                        StudentTermTeacherComment.tenant_id == tenant_id,
                        StudentTermTeacherComment.student_enrollment_id == enrollment_id,
                    )
                )
            ).scalar_one()
            or 0
        )
        progression = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentProgressionItem)
                    .where(
                        StudentProgressionItem.tenant_id == tenant_id,
                        (
                            (StudentProgressionItem.from_enrollment_id == enrollment_id)
                            | (StudentProgressionItem.to_enrollment_id == enrollment_id)
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )
        report_filters = [
            ReportCard.tenant_id == tenant_id,
            ReportCard.student_id == enrollment.student_id,
            ReportCard.academic_session_id == enrollment.academic_session_id,
        ]
        if enrollment.class_id is not None:
            report_filters.append(ReportCard.class_id == enrollment.class_id)
        report_cards = int(
            (
                await db.execute(
                    select(func.count()).select_from(ReportCard).where(*report_filters)
                )
            ).scalar_one()
            or 0
        )
        cbt_filters = [
            CBTResultIngestionItem.tenant_id == tenant_id,
            CBTResultIngestionItem.submitted_student_id == enrollment.student_id,
        ]
        if on_or_after is not None:
            cbt_filters.append(CBTResultIngestionItem.created_at >= on_or_after)
        cbt_results = int(
            (
                await db.execute(
                    select(func.count()).select_from(CBTResultIngestionItem).where(*cbt_filters)
                )
            ).scalar_one()
            or 0
        )
        return {
            "attendance": attendance,
            "results": results,
            "teacher_comments": comments,
            "report_cards": report_cards,
            "cbt_results": cbt_results,
            "progression": progression,
        }

    @staticmethod
    async def student_activity_counts_after(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        after: datetime,
    ) -> dict[str, int]:
        """Count protected student activity recorded after a lifecycle event."""

        queries = {
            "attendance": select(func.count())
            .select_from(StudentAttendanceRecord)
            .where(
                StudentAttendanceRecord.tenant_id == tenant_id,
                StudentAttendanceRecord.student_id == student_id,
                StudentAttendanceRecord.created_at > after,
            ),
            "results": select(func.count())
            .select_from(StudentSubjectResult)
            .where(
                StudentSubjectResult.tenant_id == tenant_id,
                StudentSubjectResult.student_id == student_id,
                StudentSubjectResult.created_at > after,
            ),
            "report_cards": select(func.count())
            .select_from(ReportCard)
            .where(
                ReportCard.tenant_id == tenant_id,
                ReportCard.student_id == student_id,
                ReportCard.created_at > after,
            ),
            "teacher_comments": select(func.count())
            .select_from(StudentTermTeacherComment)
            .where(
                StudentTermTeacherComment.tenant_id == tenant_id,
                StudentTermTeacherComment.student_id == student_id,
                StudentTermTeacherComment.created_at > after,
            ),
            "cbt_results": select(func.count())
            .select_from(CBTResultIngestionItem)
            .where(
                CBTResultIngestionItem.tenant_id == tenant_id,
                CBTResultIngestionItem.submitted_student_id == student_id,
                CBTResultIngestionItem.created_at > after,
            ),
            "progression": select(func.count())
            .select_from(StudentProgressionItem)
            .where(
                StudentProgressionItem.tenant_id == tenant_id,
                StudentProgressionItem.student_id == student_id,
                StudentProgressionItem.created_at > after,
            ),
        }
        return {
            name: int((await db.execute(query)).scalar_one() or 0)
            for name, query in queries.items()
        }
