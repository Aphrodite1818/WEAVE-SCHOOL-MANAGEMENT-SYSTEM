"""Harden CurriculumSubject lifecycle and historical foreign keys.

Revision ID: 20260826_curriculum_subject_lifecycle
Revises: 20260826_curriculum_container
Create Date: 2026-08-26

This is an intentional pre-launch cutover. Curriculum membership history must be
retired through lifecycle operations rather than erased by database cascades.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260826_curriculum_subject_lifecycle"
down_revision: Union[str, Sequence[str], None] = "20260826_curriculum_container"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def _drop_fk(table_name: str, column_name: str) -> None:
    op.execute(
        f"""
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
            WHERE namespace_row.nspname = '{SCHEMA}'
              AND table_row.relname = '{table_name}'
              AND constraint_row.contype = 'f'
              AND attribute_row.attname = '{column_name}'
            LIMIT 1;

            IF fk_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE {SCHEMA}.{table_name} DROP CONSTRAINT %I',
                    fk_name
                );
            END IF;
        END $$;
        """
    )


def _replace_with_restrict(
    *,
    table_name: str,
    column_name: str,
    target_table: str,
    constraint_name: str,
) -> None:
    _drop_fk(table_name, column_name)
    op.create_foreign_key(
        constraint_name,
        table_name,
        target_table,
        [column_name],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    _replace_with_restrict(
        table_name="curriculum_subjects",
        column_name="curriculum_id",
        target_table="curricula",
        constraint_name="fk_curriculum_subjects_curriculum_id_curricula",
    )
    _replace_with_restrict(
        table_name="curriculum_offerings",
        column_name="curriculum_subject_id",
        target_table="curriculum_subjects",
        constraint_name="fk_curriculum_offerings_curriculum_subject_id_curriculum_subjects",
    )
    _replace_with_restrict(
        table_name="teacher_assignments",
        column_name="curriculum_subject_id",
        target_table="curriculum_subjects",
        constraint_name="fk_teacher_assignments_curriculum_subject_id_curriculum_subjects",
    )
    _replace_with_restrict(
        table_name="teacher_assignment_lifecycle_audits",
        column_name="curriculum_subject_id",
        target_table="curriculum_subjects",
        constraint_name=(
            "fk_teacher_assignment_lifecycle_audits_curriculum_subject_id_curriculum_subjects"
        ),
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260826_curriculum_subject_lifecycle is an intentional pre-launch integrity cutover; "
        "restore a pre-migration development database if rollback is required."
    )
