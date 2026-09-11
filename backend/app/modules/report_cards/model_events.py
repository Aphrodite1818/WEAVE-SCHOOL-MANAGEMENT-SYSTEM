"""Cross-domain invalidation hooks for report-card authority.

Class-teacher assignment is mutable configuration. Changing it must not rewrite
historical comments or published report snapshots, but any current-term comment
or unsuperseded report that depended on the previous teacher is no longer
academically authoritative.
"""

from __future__ import annotations

from sqlalchemy import event, inspect, select, update

from app.modules.classes.models import ClassRoom
from app.modules.report_cards.comment_models import (
    StudentTermTeacherComment,
    TeacherCommentStatus,
)
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.models import AcademicSession, AcademicTerm
from app.modules.students.models import StudentEnrollment


@event.listens_for(ClassRoom, "after_update")
def invalidate_current_report_context_after_class_teacher_change(
    _mapper,
    connection,
    classroom: ClassRoom,
) -> None:
    """Invalidate current-term authority when a class teacher changes.

    The hook deliberately updates status/validity only. Teacher comments and
    report-card snapshots remain immutable historical evidence.
    """

    state = inspect(classroom)
    if not state.attrs.teacher_membership_id.history.has_changes():
        return

    current_session_ids = select(AcademicSession.id).where(
        AcademicSession.tenant_id == classroom.tenant_id,
        AcademicSession.is_current.is_(True),
    )
    current_term_ids = select(AcademicTerm.id).where(
        AcademicTerm.tenant_id == classroom.tenant_id,
        AcademicTerm.academic_session_id.in_(current_session_ids),
        AcademicTerm.is_current.is_(True),
    )
    current_enrollment_ids = select(StudentEnrollment.id).where(
        StudentEnrollment.tenant_id == classroom.tenant_id,
        StudentEnrollment.class_id == classroom.id,
        StudentEnrollment.is_current.is_(True),
        StudentEnrollment.academic_session_id.in_(current_session_ids),
    )

    connection.execute(
        update(StudentTermTeacherComment)
        .where(
            StudentTermTeacherComment.tenant_id == classroom.tenant_id,
            StudentTermTeacherComment.class_id == classroom.id,
            StudentTermTeacherComment.student_enrollment_id.in_(current_enrollment_ids),
            StudentTermTeacherComment.academic_term_id.in_(current_term_ids),
            StudentTermTeacherComment.status == TeacherCommentStatus.SUBMITTED,
        )
        .values(status=TeacherCommentStatus.NEEDS_REVIEW)
    )
    connection.execute(
        update(ReportCard)
        .where(
            ReportCard.tenant_id == classroom.tenant_id,
            ReportCard.class_id == classroom.id,
            ReportCard.academic_session_id.in_(current_session_ids),
            ReportCard.academic_term_id.in_(current_term_ids),
            ReportCard.superseded_at.is_(None),
        )
        .values(is_outdated=True)
    )
