"""Backfill common term offerings for the existing level curriculum.

Revision ID: 20260815_offering_backfill
Revises: 20260815_academic_hierarchy
Create Date: 2026-08-15
"""

from alembic import op


revision = "20260815_offering_backfill"
down_revision = "20260815_academic_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing level-subject mappings were implicitly applicable to every term.
    # Preserve that behavior as explicit, expected, common offerings.
    op.execute(
        """
        INSERT INTO public.subject_offerings (
            level_subject_id,
            academic_term_id,
            department_id,
            is_elective,
            tenant_id,
            id,
            created_at,
            updated_at
        )
        SELECT
            level_subject.id,
            term.id,
            NULL,
            FALSE,
            level_subject.tenant_id,
            md5(level_subject.id::text || ':' || term.id::text)::uuid,
            now(),
            now()
        FROM public.level_subjects AS level_subject
        JOIN public.academic_terms AS term
          ON term.tenant_id = level_subject.tenant_id
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM public.subject_offerings AS offering
        USING public.level_subjects AS level_subject,
              public.academic_terms AS term
        WHERE level_subject.tenant_id = term.tenant_id
          AND offering.id = md5(level_subject.id::text || ':' || term.id::text)::uuid
        """
    )
