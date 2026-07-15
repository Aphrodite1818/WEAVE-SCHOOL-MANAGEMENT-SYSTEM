
#==========================#
# student_academic_model.py#
#==========================#
import uuid
from datetime import date , datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    UUID,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class AcademicTermName(str, PyEnum):
    FIRST_TERM = "first_term"
    SECOND_TERM = "second_term"
    THIRD_TERM = "third_term"


class AcademicResultStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class AcademicSessionStatus(str , PyEnum):
    """Controlled lifecycle for an academic session"""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    CLOSING = "closing"



class StudentProgressionRunStatus(str , PyEnum):
    """Internal session-progression execution state"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"



class StudentProgressionItemStatus(str , PyEnum):
    """Outcome of processing one student during progression"""

    PROMOTED = "promoted"
    GRADUATED = "graduated"
    SKIPPED = "skipped"
    FAILED = "failed"



class StudentProgressionItemAction(str , PyEnum):
    """Academic action selected for one student"""

    PROMOTE = "promote"
    GRADUATE = "graduate"
    SKIP = "skip"



class AcademicSession(BaseModel):
    """Tenant academic session with an explicit close lifecycle."""

    __tablename__ = "academic_sessions"

    name: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[AcademicSessionStatus] = mapped_column(
        SQLEnum(
            AcademicSessionStatus,
            name="academic_session_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False,
        default=AcademicSessionStatus.DRAFT,
        server_default=AcademicSessionStatus.DRAFT.value,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    closing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "tenant_admins.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    next_academic_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_academic_session_tenant_name",
        ),
        Index(
            "uq_academic_sessions_current_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text(
                "is_current = true "
                "AND is_active = true "
                "AND status = 'open'"
            ),
        ),
        Index(
            "ix_academic_sessions_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_academic_sessions_tenant_next",
            "tenant_id",
            "next_academic_session_id",
        ),
        CheckConstraint(
            "next_academic_session_id IS NULL OR next_academic_session_id <> id",
            name="ck_academic_session_next_not_self",
        ),
        CheckConstraint(
            """
            (
                status = 'draft'
                AND closing_started_at IS NULL
                AND closed_at IS NULL
            )
            OR
            (
                status = 'open'
                AND closing_started_at IS NULL
                AND closed_at IS NULL
            )
            OR
            (
                status = 'closing'
                AND closing_started_at IS NOT NULL
                AND closed_at IS NULL
            )
            OR
            (
                status = 'closed'
                AND closing_started_at IS NOT NULL
                AND closed_at IS NOT NULL
            )
            """,
            name="ck_academic_session_status_timestamps",
        ),
        CheckConstraint(
            """
            status <> 'closed'
            OR is_current = false
            """,
            name="ck_closed_academic_session_not_current",
        ),
    )


class AcademicTerm(BaseModel):
    __tablename__ = "academic_terms"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "academic_session_id",
            "name",
            name="uq_academic_term_tenant_session_name",
        ),
        Index(
            "uq_academic_terms_current_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_current = true AND is_active = true"),
        ),
    )

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[AcademicTermName] = mapped_column(
        SQLEnum(
            AcademicTermName,
            name="academic_term_name",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )


class GradingScale(BaseModel):
    __tablename__ = "grading_scales"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "grade",
            name="uq_grading_scale_tenant_grade",
        ),
    )

    min_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    grade: Mapped[str] = mapped_column(String(10), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )


class ClassSubject(BaseModel):
    __tablename__ = "class_subjects"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "subject_id",
            name="uq_class_subject_tenant_class_subject",
        ),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_core: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )


class TeacherAssignment(BaseModel):
    __tablename__ = "teacher_assignments"

    __table_args__ = (
        Index(
            "uq_teacher_assignment_active_class_subject",
            "class_subject_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )

    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

class StudentProgressionRun(BaseModel):
    """
    Internal audit for one academic-session close operation.

    This is not a user-facing bulk-import or bulk-promotion job.
    """

    __tablename__ = "student_progression_runs"

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    next_academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "academic_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    status: Mapped[StudentProgressionRunStatus] = mapped_column(
        SQLEnum(
            StudentProgressionRunStatus,
            name="student_progression_run_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False,
        default=StudentProgressionRunStatus.PENDING,
        server_default=StudentProgressionRunStatus.PENDING.value,
    )

    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    promoted_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    graduated_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    skipped_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    initiated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "tenant_admins.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_student_progression_run_tenant_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "academic_session_id",
            name="uq_student_progression_run_tenant_session",
        ),
        Index(
            "ix_student_progression_runs_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_student_progression_runs_tenant_session",
            "tenant_id",
            "academic_session_id",
        ),
        CheckConstraint(
            """
            total_students >= 0
            AND promoted_students >= 0
            AND graduated_students >= 0
            AND skipped_students >= 0
            AND failed_students >= 0
            """,
            name="ck_progression_run_nonnegative_counts",
        ),
        CheckConstraint(
            """
            promoted_students
            + graduated_students
            + skipped_students
            + failed_students
            <= total_students
            """,
            name="ck_progression_run_count_total",
        ),
        CheckConstraint(
            """
            (
                status IN ('pending', 'processing')
                AND completed_at IS NULL
            )
            OR
            (
                status IN ('completed', 'failed')
                AND completed_at IS NOT NULL
            )
            """,
            name="ck_progression_run_completion_consistency",
        ),
    )


class StudentProgressionItem(BaseModel):
    """Audit outcome for one student in one progression run."""

    __tablename__ = "student_progression_items"

    progression_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "student_progression_runs.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "students.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    from_enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "student_enrollments.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    to_enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "student_enrollments.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    from_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "classes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    to_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "classes.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    action: Mapped[StudentProgressionItemAction] = mapped_column(
        SQLEnum(
            StudentProgressionItemAction,
            name="student_progression_item_action",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False,
    )

    status: Mapped[StudentProgressionItemStatus] = mapped_column(
        SQLEnum(
            StudentProgressionItemStatus,
            name="student_progression_item_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "progression_run_id",
            "student_id",
            name="uq_progression_item_run_student",
        ),
        Index(
            "ix_progression_items_tenant_run",
            "tenant_id",
            "progression_run_id",
        ),
        Index(
            "ix_progression_items_tenant_student",
            "tenant_id",
            "student_id",
        ),
        Index(
            "ix_progression_items_tenant_status",
            "tenant_id",
            "status",
        ),
        CheckConstraint(
            """
            action <> 'promote'
            OR to_class_id IS NOT NULL
            """,
            name="ck_progression_item_promotion_has_target",
        ),
        CheckConstraint(
            """
            action <> 'graduate'
            OR to_class_id IS NULL
            """,
            name="ck_progression_item_graduation_no_target",
        ),
    )







    
class ClassSubjectTeacher(BaseModel):
    __tablename__ = "class_subject_teachers"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "subject_id",
            name="uq_class_subject_teacher_tenant_class_subject",
        ),
        Index(
            "ix_class_subject_teachers_tenant_teacher_active",
            "tenant_id",
            "teacher_id",
            "is_active",
        ),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_core: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )


class StudentSubjectResult(BaseModel):
    __tablename__ = "student_subject_results"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "class_subject_teacher_id",
            "academic_session_id",
            "academic_term_id",
            name="uq_student_subject_result_scope",
        ),
        Index("ix_student_subject_results_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_subject_results_tenant_class", "tenant_id", "class_id"),
        Index("ix_student_subject_results_tenant_teacher", "tenant_id", "teacher_id"),
        Index("ix_student_subject_results_tenant_status", "tenant_id", "status"),
        Index(
            "ix_student_subject_results_student_period",
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
        ),
        Index(
            "ix_student_subject_results_class_period_status",
            "tenant_id",
            "class_id",
            "academic_session_id",
            "academic_term_id",
            "status",
        ),
        Index(
            "ix_student_subject_results_teacher_period",
            "tenant_id",
            "teacher_id",
            "academic_session_id",
            "academic_term_id",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    class_subject_teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("class_subject_teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    test_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    assessment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    exam_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AcademicResultStatus] = mapped_column(
        SQLEnum(
            AcademicResultStatus,
            name="academic_result_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AcademicResultStatus.DRAFT,
        server_default=AcademicResultStatus.DRAFT.value,
    )
    recorded_by_actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_by_actor_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
