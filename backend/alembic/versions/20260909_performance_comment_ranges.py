"""Cut report comments from grade mappings to performance ranges.

Revision ID: 20260909_perf_comment_ranges
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

revision: str = "20260909_perf_comment_ranges"
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

    # The service rejects overlap for a friendly API error. This trigger is the
    # concurrency-safe database invariant: it serializes writes per owner and
    # rejects every distinct inclusive overlap. Exact duplicate ranges remain
    # valid so an owner can keep several wording choices for the same band.
    op.execute(
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
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_comment_templates_no_distinct_range_overlap
        BEFORE INSERT OR UPDATE OF tenant_id, owner_type, tenant_admin_id,
            teacher_membership_id, minimum_score, maximum_score, status
        ON public.comment_templates
        FOR EACH ROW
        EXECUTE FUNCTION public.enforce_comment_template_range_overlap()
        """
    )


def downgrade() -> None:
    # Downgrade is also destructive; the removed grade mappings cannot be
    # reconstructed and intentionally remain empty.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_comment_templates_no_distinct_range_overlap "
        "ON public.comment_templates"
    )
    op.execute("DROP FUNCTION IF EXISTS public.enforce_comment_template_range_overlap()")

    op.execute(
        "UPDATE public.report_cards SET principal_comment_source_template_id = NULL "
        "WHERE principal_comment_source_template_id IS NOT NULL"
    )
    op.execute(
        "UPDATE public.student_term_teacher_comments SET source_template_id = NULL "
        "WHERE source_template_id IS NOT NULL"
    )
    op.execute("DELETE FROM public.comment_templates")

    op.drop_index(
        "ix_comment_templates_owner_range",
        table_name="comment_templates",
        schema="public",
    )
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
        sa.ForeignKeyConstraint(
            ["comment_template_id"],
            ["public.comment_templates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grading_scale_id"],
            ["public.grading_scales.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
            ondelete="CASCADE",
        ),
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
