import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class ReportCardStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReportCard(BaseModel):
    """Immutable issuance revision plus historical display snapshots."""

    __tablename__ = "report_cards"

    __table_args__ = (
        Index("ix_report_cards_tenant_student", "tenant_id", "student_id"),
        Index("ix_report_cards_tenant_status", "tenant_id", "status"),
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            "version",
            name="uq_report_cards_student_period_version",
        ),
        Index(
            "uq_report_cards_current_published_period",
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("status = 'published' AND superseded_at IS NULL"),
        ),
        Index(
            "uq_report_cards_current_draft_period",
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("status = 'draft' AND superseded_at IS NULL"),
        ),
        CheckConstraint(
            "status <> 'published' OR (published_at IS NOT NULL AND published_by IS NOT NULL)",
            name="ck_report_cards_published_metadata",
        ),
        CheckConstraint(
            "superseded_at IS NULL OR is_outdated = true",
            name="ck_report_cards_superseded_is_outdated",
        ),
        CheckConstraint(
            "teacher_comment_source IS NULL OR teacher_comment_source IN ('teacher_submission', 'admin_override')",
            name="ck_report_cards_teacher_comment_source",
        ),
        CheckConstraint(
            "teacher_comment_source <> 'admin_override' OR "
            "(teacher_comment_override_reason IS NOT NULL "
            "AND teacher_comment_override_admin_id IS NOT NULL "
            "AND teacher_comment_override_at IS NOT NULL)",
            name="ck_report_cards_admin_override_provenance",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    academic_level_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=True,
    )
    academic_level_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_level_departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_level_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    class_name_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    class_arm_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_name_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    teacher_name_snapshot: Mapped[str | None] = mapped_column(String(210), nullable=True)
    total_score: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    average_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_out_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_teacher_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_comment_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    teacher_comment_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    teacher_comment_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_comment_override_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    teacher_comment_override_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    principal_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    principal_comment_source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comment_templates.id", ondelete="RESTRICT"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    replaces_report_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_cards.id", ondelete="RESTRICT"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_outdated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ReportCardStatus] = mapped_column(
        SQLEnum(
            ReportCardStatus,
            name="report_card_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ReportCardStatus.DRAFT,
        server_default=ReportCardStatus.DRAFT.value,
    )
    generated_by_actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_by_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReportCardSubjectLine(BaseModel):
    __tablename__ = "report_card_subject_lines"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "report_card_id",
            "subject_id",
            name="uq_report_card_lines_card_subject",
        ),
    )

    report_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_subject_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_subject_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subject_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    teacher_name: Mapped[str | None] = mapped_column(String(210), nullable=True)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    grade: Mapped[str] = mapped_column(String(10), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ReportCardSubjectComponent(BaseModel):
    __tablename__ = "report_card_subject_components"

    report_card_subject_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_card_subject_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_components.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "report_card_subject_line_id",
            "assessment_component_id",
            name="uq_report_card_component_line_component",
        ),
        CheckConstraint(
            "score >= 0 AND maximum_score > 0 AND score <= maximum_score",
            name="ck_report_card_component_score",
        ),
        Index(
            "ix_report_card_subject_components_tenant_line_position",
            "tenant_id",
            "report_card_subject_line_id",
            "position",
        ),
    )
