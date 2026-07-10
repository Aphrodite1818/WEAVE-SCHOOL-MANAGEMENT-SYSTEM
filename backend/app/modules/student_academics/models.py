import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
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


class AcademicSession(BaseModel):
    __tablename__ = "academic_sessions"

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
            postgresql_where=text("is_current = true AND is_active = true"),
        ),
    )

    name: Mapped[str] = mapped_column(String(30), nullable=False)
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
