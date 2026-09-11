"""Add canonical placement outcomes and report-comment authority.

Revision ID: 20260905_placement_comments
Revises: 20260905_cbt_sync_enum_repair
Create Date: 2026-09-05

This is a pre-launch contract cutover. The enrollment enum additions are
PostgreSQL-safe and intentionally irreversible: PostgreSQL cannot safely remove
an enum value while preserving rows that may use it. Downgrade therefore fails
explicitly instead of pretending to reverse potentially historical evidence.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_placement_comments"
down_revision: Union[str, Sequence[str], None] = "20260905_cbt_sync_enum_repair"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # PostgreSQL enum additions must be committed independently before code can
    # rely on them in every server version we support.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE public.student_enrollment_outcome "
            "ADD VALUE IF NOT EXISTS 'class_placed'"
        )
        op.execute(
            "ALTER TYPE public.student_enrollment_outcome "
            "ADD VALUE IF NOT EXISTS 'level_reassigned'"
        )

    bind = op.get_bind()
    owner_type = postgresql.ENUM(
        "tenant_admin",
        "teacher",
        name="comment_template_owner_type",
        schema=SCHEMA,
    )
    template_status = postgresql.ENUM(
        "active",
        "inactive",
        "archived",
        name="comment_template_status",
        schema=SCHEMA,
    )
    teacher_comment_status = postgresql.ENUM(
        "draft",
        "submitted",
        "needs_review",
        name="teacher_comment_status",
        schema=SCHEMA,
    )
    owner_type.create(bind, checkfirst=True)
    template_status.create(bind, checkfirst=True)
    teacher_comment_status.create(bind, checkfirst=True)

    owner_type_col = postgresql.ENUM(
        "tenant_admin",
        "teacher",
        name="comment_template_owner_type",
        schema=SCHEMA,
        create_type=False,
    )
    template_status_col = postgresql.ENUM(
        "active",
        "inactive",
        "archived",
        name="comment_template_status",
        schema=SCHEMA,
        create_type=False,
    )
    teacher_comment_status_col = postgresql.ENUM(
        "draft",
        "submitted",
        "needs_review",
        name="teacher_comment_status",
        schema=SCHEMA,
        create_type=False,
    )

    op.create_table(
        "comment_templates",
        *_base_columns(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("owner_type", owner_type_col, nullable=False),
        sa.Column(
            "tenant_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenant_admins.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "teacher_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.teacher_memberships.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            template_status_col,
            server_default="active",
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_comment_templates_name_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(text)) > 0",
            name="ck_comment_templates_text_nonempty",
        ),
        sa.CheckConstraint(
            "(owner_type = 'tenant_admin' AND tenant_admin_id IS NOT NULL "
            "AND teacher_membership_id IS NULL) OR "
            "(owner_type = 'teacher' AND teacher_membership_id IS NOT NULL "
            "AND tenant_admin_id IS NULL)",
            name="ck_comment_templates_single_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_comment_templates_tenant_status",
        "comment_templates",
        ["tenant_id", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_comment_templates_admin_owner",
        "comment_templates",
        ["tenant_id", "tenant_admin_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_comment_templates_teacher_owner",
        "comment_templates",
        ["tenant_id", "teacher_membership_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "comment_template_grade_mappings",
        *_base_columns(),
        sa.Column(
            "comment_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.comment_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grading_scale_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.grading_scales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "comment_template_id",
            "grading_scale_id",
            name="uq_comment_template_grade_mapping",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_comment_template_grade_mappings_grade",
        "comment_template_grade_mappings",
        ["tenant_id", "grading_scale_id", "is_default"],
        schema=SCHEMA,
    )

    op.create_table(
        "student_term_teacher_comments",
        *_base_columns(),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_enrollment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.student_enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "teacher_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.teacher_memberships.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("average_snapshot", sa.Numeric(7, 2), nullable=False),
        sa.Column("grade_snapshot", sa.String(length=10), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column(
            "source_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.comment_templates.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            teacher_comment_status_col,
            server_default="draft",
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status <> 'submitted' OR submitted_at IS NOT NULL",
            name="ck_teacher_comment_submitted_at",
        ),
        sa.CheckConstraint(
            "length(trim(comment_text)) > 0",
            name="ck_teacher_comment_text_nonempty",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "student_enrollment_id",
            "academic_term_id",
            "teacher_membership_id",
            name="uq_student_term_teacher_comment_context",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_comments_student_period",
        "student_term_teacher_comments",
        ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_comments_teacher_period",
        "student_term_teacher_comments",
        ["tenant_id", "teacher_membership_id", "academic_session_id", "academic_term_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_comments_status",
        "student_term_teacher_comments",
        ["tenant_id", "status"],
        schema=SCHEMA,
    )

    op.create_table(
        "teacher_comment_overrides",
        *_base_columns(),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_enrollment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.student_enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenant_admins.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.CheckConstraint(
            "length(trim(comment_text)) > 0",
            name="ck_teacher_override_text_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_teacher_override_reason_nonempty",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_comment_overrides_student_period",
        "teacher_comment_overrides",
        [
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            "created_at",
        ],
        schema=SCHEMA,
    )

    # Report revisions snapshot mutable display context and preserve audited
    # teacher-comment provenance.
    op.add_column(
        "report_cards",
        sa.Column(
            "academic_level_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_levels.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column(
            "academic_level_department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.academic_level_departments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    for name, length in (
        ("academic_level_name_snapshot", 100),
        ("class_name_snapshot", 160),
        ("class_arm_snapshot", 100),
        ("department_name_snapshot", 150),
        ("teacher_name_snapshot", 210),
    ):
        op.add_column(
            "report_cards",
            sa.Column(name, sa.String(length=length), nullable=True),
            schema=SCHEMA,
        )
    op.add_column(
        "report_cards",
        sa.Column("teacher_comment_source", sa.String(length=30), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column("teacher_comment_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column("teacher_comment_override_reason", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column(
            "teacher_comment_override_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenant_admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column("teacher_comment_override_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column(
            "principal_comment_source_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.comment_templates.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "report_cards",
        sa.Column(
            "replaces_report_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.report_cards.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    op.execute("DROP INDEX IF EXISTS public.ix_report_cards_active_student_period")
    op.create_unique_constraint(
        "uq_report_cards_student_period_version",
        "report_cards",
        [
            "tenant_id",
            "student_id",
            "academic_session_id",
            "academic_term_id",
            "version",
        ],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_report_cards_current_published_period",
        "report_cards",
        ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published' AND superseded_at IS NULL"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_report_cards_current_draft_period",
        "report_cards",
        ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft' AND superseded_at IS NULL"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_report_cards_teacher_comment_source",
        "report_cards",
        "teacher_comment_source IS NULL OR teacher_comment_source IN "
        "('teacher_submission', 'admin_override')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_report_cards_admin_override_provenance",
        "report_cards",
        "teacher_comment_source <> 'admin_override' OR "
        "(teacher_comment_override_reason IS NOT NULL "
        "AND teacher_comment_override_admin_id IS NOT NULL "
        "AND teacher_comment_override_at IS NOT NULL)",
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260905_placement_comments adds durable placement enum values and historical "
        "report/comment evidence. PostgreSQL enum value removal is not safely reversible; "
        "restore a pre-migration database snapshot if rollback is required."
    )
