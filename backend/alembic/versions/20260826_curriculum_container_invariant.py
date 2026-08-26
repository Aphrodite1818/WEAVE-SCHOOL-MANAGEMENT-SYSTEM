"""Enforce one persistent Curriculum container for every published academic level.

Revision ID: 20260826_curriculum_container
Revises: 20260826_subject_lifecycle
Create Date: 2026-08-26

This is an intentional pre-launch cutover. Published levels are backfilled with
exactly one Curriculum container, stale empty draft containers are removed, and
AcademicLevel deletion can no longer cascade through curriculum history.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260826_curriculum_container"
down_revision: Union[str, Sequence[str], None] = "20260826_subject_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def _drop_curriculum_level_fk() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT constraint_row.conname
            INTO fk_name
            FROM pg_constraint AS constraint_row
            JOIN pg_class AS table_row
              ON table_row.oid = constraint_row.conrelid
            JOIN pg_namespace AS namespace_row
              ON namespace_row.oid = table_row.relnamespace
            JOIN pg_attribute AS attribute_row
              ON attribute_row.attrelid = table_row.oid
             AND attribute_row.attnum = ANY(constraint_row.conkey)
            WHERE namespace_row.nspname = 'public'
              AND table_row.relname = 'curricula'
              AND constraint_row.contype = 'f'
              AND attribute_row.attname = 'academic_level_id'
            LIMIT 1;

            IF fk_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.curricula DROP CONSTRAINT %I',
                    fk_name
                );
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    # A DRAFT level should never own curriculum content. Refuse to erase anything
    # meaningful if old data somehow violated that rule, then clean only empty
    # containers created by the former GET-side lazy creation behavior.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.curricula AS curriculum
                JOIN public.academic_levels AS level
                  ON level.id = curriculum.academic_level_id
                 AND level.tenant_id = curriculum.tenant_id
                WHERE level.status = 'draft'
                  AND EXISTS (
                      SELECT 1
                      FROM public.curriculum_subjects AS curriculum_subject
                      WHERE curriculum_subject.curriculum_id = curriculum.id
                        AND curriculum_subject.tenant_id = curriculum.tenant_id
                  )
            ) THEN
                RAISE EXCEPTION
                    'draft academic levels contain curriculum subjects; clean this invalid development data before upgrading';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DELETE FROM public.curricula AS curriculum
        USING public.academic_levels AS level
        WHERE level.id = curriculum.academic_level_id
          AND level.tenant_id = curriculum.tenant_id
          AND level.status = 'draft'
          AND NOT EXISTS (
              SELECT 1
              FROM public.curriculum_subjects AS curriculum_subject
              WHERE curriculum_subject.curriculum_id = curriculum.id
                AND curriculum_subject.tenant_id = curriculum.tenant_id
          )
        """
    )

    # ACTIVE/INACTIVE/ARCHIVED levels have crossed the publication boundary and
    # therefore must permanently own one Curriculum container. Use deterministic
    # UUIDs so the backfill is repeatable without requiring a database extension.
    op.execute(
        """
        INSERT INTO public.curricula (
            tenant_id,
            id,
            academic_level_id,
            created_at,
            updated_at
        )
        SELECT
            level.tenant_id,
            md5(level.tenant_id::text || ':curriculum:' || level.id::text)::uuid,
            level.id,
            now(),
            now()
        FROM public.academic_levels AS level
        WHERE level.status IN ('active', 'inactive', 'archived')
          AND NOT EXISTS (
              SELECT 1
              FROM public.curricula AS curriculum
              WHERE curriculum.tenant_id = level.tenant_id
                AND curriculum.academic_level_id = level.id
          )
        ON CONFLICT (tenant_id, academic_level_id) DO NOTHING
        """
    )

    _drop_curriculum_level_fk()
    op.create_foreign_key(
        "fk_curricula_academic_level_id_academic_levels",
        "curricula",
        "academic_levels",
        ["academic_level_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260826_curriculum_container is an intentional pre-launch invariant cutover; "
        "restore a pre-migration development database if rollback is required."
    )
