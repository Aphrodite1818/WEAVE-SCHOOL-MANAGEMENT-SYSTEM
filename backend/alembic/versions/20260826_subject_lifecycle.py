"""Harden Subject lifecycle integrity and curriculum history.

Revision ID: 20260826_subject_lifecycle
Revises: 20260826_arm_label_lifecycle
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260826_subject_lifecycle"
down_revision: Union[str, Sequence[str], None] = "20260826_arm_label_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def _drop_curriculum_subject_subject_fk() -> None:
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
              AND table_row.relname = 'curriculum_subjects'
              AND constraint_row.contype = 'f'
              AND attribute_row.attname = 'subject_id'
            LIMIT 1;

            IF fk_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.curriculum_subjects DROP CONSTRAINT %I',
                    fk_name
                );
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _drop_curriculum_subject_subject_fk()
    op.create_foreign_key(
        "fk_curriculum_subjects_subject_id_subjects",
        "curriculum_subjects",
        "subjects",
        ["subject_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )

    op.execute(
        "ALTER TABLE public.subjects "
        "DROP CONSTRAINT IF EXISTS ck_subjects_archived_requires_inactive"
    )
    op.create_check_constraint(
        "ck_subjects_archive_metadata_consistency",
        "subjects",
        """
        (archived_at IS NULL AND archived_by_admin_id IS NULL)
        OR (archived_at IS NOT NULL AND is_active = false)
        """,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_subjects_archive_metadata_consistency",
        "subjects",
        type_="check",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_subjects_archived_requires_inactive",
        "subjects",
        "archived_at IS NULL OR is_active = false",
        schema=SCHEMA,
    )

    _drop_curriculum_subject_subject_fk()
    op.create_foreign_key(
        "fk_curriculum_subjects_subject_id_subjects",
        "curriculum_subjects",
        "subjects",
        ["subject_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
