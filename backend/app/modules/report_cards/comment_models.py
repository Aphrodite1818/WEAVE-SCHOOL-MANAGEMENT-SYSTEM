"""Performance-range report-comment configuration and teacher comment evidence."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DDL,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


def enum_values(enum_cls: type[PyEnum]) -> list[str]:
    return [str(item.value) for item in enum_cls]


class CommentTemplateOwnerType(str, PyEnum):
    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"


class CommentTemplateStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TeacherCommentStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    NEEDS_REVIEW = "needs_review"


class TeacherCommentSource(str, PyEnum):
    TEACHER_SUBMISSION = "teacher_submission"
    ADMIN_OVERRIDE = "admin_override"


class CommentTemplate(BaseModel):
    """Reusable wording for one inclusive overall-performance range.

    Owners may keep several comments for the *same exact* range. Exactly one
    active comment for an active range is selected as the default by the
    service. Distinct ranges are not allowed to overlap.
    """

    __tablename__ = "comment_templates"

    text: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    owner_type: Mapped[CommentTemplateOwnerType] = mapped_column(
        SQLEnum(
            CommentTemplateOwnerType,
            name="comment_template_owner_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    tenant_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="RESTRICT"),
        nullable=True,
    )
    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[CommentTemplateStatus] = mapped_column(
        SQLEnum(
            CommentTemplateStatus,
            name="comment_template_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=CommentTemplateStatus.ACTIVE,
        server_default=CommentTemplateStatus.ACTIVE.value,
    )

    __table_args__ = (
        CheckConstraint("length(trim(text)) > 0", name="ck_comment_templates_text_nonempty"),
        CheckConstraint(
            "minimum_score >= 0 AND maximum_score <= 100 AND minimum_score <= maximum_score",
            name="ck_comment_templates_score_range",
        ),
        CheckConstraint(
            "is_default = false OR status = 'active'",
            name="ck_comment_templates_default_active",
        ),
        CheckConstraint(
            "(owner_type = 'tenant_admin' AND tenant_admin_id IS NOT NULL AND teacher_membership_id IS NULL) "
            "OR (owner_type = 'teacher' AND teacher_membership_id IS NOT NULL AND tenant_admin_id IS NULL)",
            name="ck_comment_templates_single_owner",
        ),
        Index("ix_comment_templates_tenant_status", "tenant_id", "status"),
        Index("ix_comment_templates_admin_owner", "tenant_id", "tenant_admin_id"),
        Index("ix_comment_templates_teacher_owner", "tenant_id", "teacher_membership_id"),
        Index(
            "ix_comment_templates_owner_range",
            "tenant_id",
            "owner_type",
            "minimum_score",
            "maximum_score",
            "status",
        ),
    )


event.listen(
    CommentTemplate.__table__,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION public.enforce_comment_template_range_overlap()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            owner_key text;
        BEGIN
            IF NEW.status = 'archived' THEN
                RETURN NEW;
            END IF;

            owner_key := NEW.tenant_id::text || ':' || NEW.owner_type::text || ':' ||
                COALESCE(NEW.tenant_admin_id::text, NEW.teacher_membership_id::text, 'none');
            PERFORM pg_advisory_xact_lock(hashtextextended(owner_key, 0));

            IF EXISTS (
                SELECT 1
                FROM public.comment_templates existing
                WHERE existing.tenant_id = NEW.tenant_id
                  AND existing.owner_type = NEW.owner_type
                  AND existing.status <> 'archived'
                  AND existing.id <> NEW.id
                  AND (
                    (NEW.owner_type = 'tenant_admin'
                     AND existing.tenant_admin_id = NEW.tenant_admin_id)
                    OR
                    (NEW.owner_type = 'teacher'
                     AND existing.teacher_membership_id = NEW.teacher_membership_id)
                  )
                  AND NEW.minimum_score <= existing.maximum_score
                  AND NEW.maximum_score >= existing.minimum_score
                  AND NOT (
                    NEW.minimum_score = existing.minimum_score
                    AND NEW.maximum_score = existing.maximum_score
                  )
            ) THEN
                RAISE EXCEPTION 'Comment performance ranges cannot overlap'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_comment_templates_no_distinct_range_overlap';
            END IF;

            RETURN NEW;
        END;
        $$
        """
    ).execute_if(dialect="postgresql"),
)
event.listen(
    CommentTemplate.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_comment_templates_no_distinct_range_overlap
        BEFORE INSERT OR UPDATE OF tenant_id, owner_type, tenant_admin_id,
            teacher_membership_id, minimum_score, maximum_score, status
        ON public.comment_templates
        FOR EACH ROW
        EXECUTE FUNCTION public.enforce_comment_template_range_overlap()
        """
    ).execute_if(dialect="postgresql"),
)


class StudentTermTeacherComment(BaseModel):
    """Teacher-authored term comment evidence that exists before report generation."""

    __tablename__ = "student_term_teacher_comments"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_enrollments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Historical column name retained in the physical schema for report evidence;
    # its value is now the canonical weighted overall-performance percentage.
    average_snapshot: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    grade_snapshot: Mapped[str] = mapped_column(String(10), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comment_templates.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[TeacherCommentStatus] = mapped_column(
        SQLEnum(
            TeacherCommentStatus,
            name="teacher_comment_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=TeacherCommentStatus.DRAFT,
        server_default=TeacherCommentStatus.DRAFT.value,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "student_enrollment_id",
            "academic_term_id",
            "teacher_membership_id",
            name="uq_student_term_teacher_comment_context",
        ),
        CheckConstraint(
            "status <> 'submitted' OR submitted_at IS NOT NULL",
            name="ck_teacher_comment_submitted_at",
        ),
        CheckConstraint(
            "length(trim(comment_text)) > 0",
            name="ck_teacher_comment_text_nonempty",
        ),
        Index(
            "ix_teacher_comments_student_period",
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
        ),
        Index(
            "ix_teacher_comments_teacher_period",
            "tenant_id",
            "teacher_membership_id",
            "academic_session_id",
            "academic_term_id",
        ),
        Index("ix_teacher_comments_status", "tenant_id", "status"),
    )


class TeacherCommentOverride(BaseModel):
    """Audited admin replacement for the class-teacher comment requirement."""

    __tablename__ = "teacher_comment_overrides"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_enrollments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_admins.id", ondelete="RESTRICT"), nullable=False
    )
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)

    __table_args__ = (
        CheckConstraint("length(trim(comment_text)) > 0", name="ck_teacher_override_text_nonempty"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_teacher_override_reason_nonempty"),
        Index(
            "ix_teacher_comment_overrides_student_period",
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            "created_at",
        ),
    )
