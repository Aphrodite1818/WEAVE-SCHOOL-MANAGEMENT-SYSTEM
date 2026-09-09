"""Cut report comments from grade mappings to performance ranges.

Revision ID: 20260909_performance_comment_ranges
Revises: 20260908_cbt_audit_display
Create Date: 2026-09-09

This is intentionally destructive. Legacy grade-linked template configuration is
not migrated or preserved. Historical report/comment text remains intact, but
its obsolete source-template reference is cleared before the old configuration
rows are deleted.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_performance_comment_ranges"
down_revision: Union[str, Sequence[str], None] = "20260908_cbt_audit_display"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve historical rendered wording while severing obsolete grade-template
    # provenance. No legacy template data survives this cutover.
    op.execute(
        "UPDATE public.report_cards SET principal_comment_source_template_id = NULL "
        "WHERE principal_comment_source_template_id IS NOT NULL"
    )
    op.execute(
        "UPDATE public.student_term_teacher_comments SET source_template_id = NULL "
        "WHERE source_template_id IS NOT NULL"
    )
    op.execute("DELETE FROM public.comment_template_grade_mappings")
    op.execute("DELETE FROM public.comment_templates")

    op.drop_table("comment_template_grade_mappings", schema="public")
    op.drop_constraint(
        "ck_comment_templates_name_nonempty",
        "comment_templates",
        schema="public",
        type_="check",
    )
    op.drop_column("comment_templates", "name", schema="public")

    op.add_column(
        "comment_templates",
        sa.Column("minimum_score", sa.Numeric(5, 2), nullable=False),
        schema="public",
    )
    op.add_column(
        "comment_templates",
        sa.Column("maximum_score", sa.Numeric(5, 2), nullable=False),
        schema="public",
    )
    op.add_column(
        "comment_templates",
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="public",
    )
    op.create_check_constraint(
        "ck_comment_templates_score_range",
        "comment_templates",
        "minimum_score >= 0 AND maximum_score <= 100 AND minimum_score <= maximum_score",
        schema="public",
    )
    op.create_check_constraint(
        "ck_comment_templates_default_active",
        "comment_templates",
        "is_default = false OR status = 'active'",
        schema="public",
    )
    op.create_index(
        "ix_comment_templates_owner_range",
        "comment_templates",
        ["tenant_id", "owner_type", "minimum_score", "maximum_score", "status"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    # Downgrade is also destructive; the removed grade mappings cannot be
    # reconstructed and intentionally remain empty.
    op.execute(
        "UPDATE public.report_cards SET principal_comment_source_template_id = NULL "
        "WHERE principal_comment_source_template_id IS NOT NULL"
    )
    op.execute(
        "UPDATE public.student_term_teacher_comments SET source_template_id = NULL "
        "WHERE source_template_id IS NOT NULL"
    )
    op.execute("DELETE FROM public.comment_templates")

    op.drop_index("ix_comment_templates_owner_range", table_name="comment_templates", schema="public")
    op.drop_constraint(
        "ck_comment_templates_default_active",
        "comment_templates",
        schema="public",
        type_="check",
    )
    op.drop_constraint(
        "ck_comment_templates_score_range",
        "comment_templates",
        schema="public",
        type_="check",
    )
    op.drop_column("comment_templates", "is_default", schema="public")
    op.drop_column("comment_templates", "maximum_score", schema="public")
    op.drop_column("comment_templates", "minimum_score", schema="public")
    op.add_column(
        "comment_templates",
        sa.Column("name", sa.String(length=120), nullable=False),
        schema="public",
    )
    op.create_check_constraint(
        "ck_comment_templates_name_nonempty",
        "comment_templates",
        "length(trim(name)) > 0",
        schema="public",
    )
    op.create_table(
        "comment_template_grade_mappings",
        sa.Column("comment_template_id", sa.Uuid(), nullable=False),
        sa.Column("grading_scale_id", sa.Uuid(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_template_id"], ["public.comment_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grading_scale_id"], ["public.grading_scales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "comment_template_id",
            "grading_scale_id",
            name="uq_comment_template_grade_mapping",
        ),
        schema="public",
    )
    op.create_index(
        "ix_comment_template_grade_mappings_grade",
        "comment_template_grade_mappings",
        ["tenant_id", "grading_scale_id", "is_default"],
        unique=False,
        schema="public",
    )
