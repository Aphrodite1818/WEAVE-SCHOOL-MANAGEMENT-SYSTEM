"""Read model for the class-teacher report-comment dashboard."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.comment_schemas import (
    TeacherCommentClassScope,
    TeacherCommentDashboardSummary,
)
from app.modules.student_academics.models import AcademicSession, AcademicTerm
from app.modules.teachers.models import TeacherMembership


class TeacherCommentSummaryService:
    @staticmethod
    async def build(db, *, teacher: TeacherMembership) -> TeacherCommentDashboardSummary:
        tenant_id = teacher.tenant_id
        class_rows = (
            await db.execute(
                select(ClassRoom, AcademicLevel, ArmLabel)
                .join(
                    AcademicLevel,
                    (AcademicLevel.id == ClassRoom.academic_level_id)
                    & (AcademicLevel.tenant_id == tenant_id),
                )
                .join(
                    ArmLabel,
                    (ArmLabel.id == ClassRoom.arm_label_id)
                    & (ArmLabel.tenant_id == tenant_id),
                )
                .where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.teacher_membership_id == teacher.id,
                    ClassRoom.is_active.is_(True),
                    ClassRoom.archived_at.is_(None),
                )
                .order_by(AcademicLevel.position, ArmLabel.label)
            )
        ).all()
        scopes = [
            TeacherCommentClassScope(
                class_id=classroom.id,
                academic_level_id=classroom.academic_level_id,
                class_name=f"{level.name} {arm.label}".strip(),
            )
            for classroom, level, arm in class_rows
        ]

        session = (
            await db.execute(
                select(AcademicSession).where(
                    AcademicSession.tenant_id == tenant_id,
                    AcademicSession.is_current.is_(True),
                )
            )
        ).scalar_one_or_none()
        term = None
        if session is not None:
            term = (
                await db.execute(
                    select(AcademicTerm).where(
                        AcademicTerm.tenant_id == tenant_id,
                        AcademicTerm.academic_session_id == session.id,
                        AcademicTerm.is_current.is_(True),
                    )
                )
            ).scalar_one_or_none()

        if session is None or term is None or not scopes:
            return TeacherCommentDashboardSummary(
                classes=scopes,
                class_teacher_class_count=len(scopes),
                academic_session_id=session.id if session else None,
                academic_term_id=term.id if term else None,
            )

        requiring = drafts = submitted = needs_review = total_ready = 0
        for scope in scopes:
            roster = await ReportCommentService.list_teacher_students(
                db,
                teacher=teacher,
                class_id=scope.class_id,
                academic_session_id=session.id,
                academic_term_id=term.id,
            )
            for row in roster.items:
                if row.academic_ready:
                    total_ready += 1
                status = str(row.comment_status or "").lower()
                if status == "draft":
                    drafts += 1
                elif status == "submitted":
                    submitted += 1
                elif status == "needs_review":
                    needs_review += 1
                if row.academic_ready and status != "submitted":
                    requiring += 1

        completion = (
            (Decimal(submitted) / Decimal(total_ready) * Decimal("100"))
            if total_ready
            else Decimal("0")
        )
        return TeacherCommentDashboardSummary(
            classes=scopes,
            class_teacher_class_count=len(scopes),
            students_requiring_comments=requiring,
            draft_comments=drafts,
            submitted_comments=submitted,
            needs_review_comments=needs_review,
            comment_completion_percent=completion.quantize(Decimal("0.01")),
            academic_session_id=session.id,
            academic_term_id=term.id,
        )
