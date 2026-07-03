"""add normalized subject identity

Revision ID: 20260702_subject_identity
Revises: 20260702_teacher_assign_active
Create Date: 2026-07-02 00:00:00.000002

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260702_subject_identity"
down_revision: Union[str, Sequence[str], None] = "20260702_teacher_assign_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _baseline_already_created_subject_identity() -> bool:
    """Return True when the staging baseline already emitted the subject identity schema.

    The staging baseline builds the current metadata with ``create_all``. On a
    fresh staging database, the normalized subject columns and their unique
    constraints already exist, so re-applying this historical migration would
    raise duplicate-column / duplicate-constraint errors.
    """

    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "subjects" not in inspector.get_table_names():
        return False

    subject_columns = {column["name"] for column in inspector.get_columns("subjects")}
    return {"normalized_name", "normalized_code"}.issubset(subject_columns)


def upgrade() -> None:
    if _baseline_already_created_subject_identity():
        return

    op.add_column("subjects", sa.Column("normalized_name", sa.String(length=120), nullable=True))
    op.add_column("subjects", sa.Column("normalized_code", sa.String(length=40), nullable=True))

    op.execute(
        """
        UPDATE subjects
        SET
            normalized_name = lower(regexp_replace(trim(name), '\\s+', ' ', 'g')),
            normalized_code = NULLIF(upper(regexp_replace(trim(COALESCE(code, '')), '\\s+', '', 'g')), '')
        """
    )

    # Avoid migration failure on historical duplicate display names by making older duplicates unique.
    # New application code prevents these duplicates going forward.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, normalized_name
                    ORDER BY created_at DESC, id DESC
                ) AS rn
            FROM subjects
            WHERE normalized_name IS NOT NULL
        )
        UPDATE subjects AS subject
        SET normalized_name = subject.normalized_name || '-' || substring(subject.id::text, 1, 8)
        FROM ranked
        WHERE subject.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, normalized_code
                    ORDER BY created_at DESC, id DESC
                ) AS rn
            FROM subjects
            WHERE normalized_code IS NOT NULL
        )
        UPDATE subjects AS subject
        SET normalized_code = subject.normalized_code || '-' || substring(subject.id::text, 1, 8)
        FROM ranked
        WHERE subject.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.alter_column("subjects", "normalized_name", existing_type=sa.String(length=120), nullable=False)
    op.create_unique_constraint(
        "uq_subject_tenant_normalized_name",
        "subjects",
        ["tenant_id", "normalized_name"],
    )
    op.create_unique_constraint(
        "uq_subject_tenant_normalized_code",
        "subjects",
        ["tenant_id", "normalized_code"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_subject_tenant_normalized_code", "subjects", type_="unique")
    op.drop_constraint("uq_subject_tenant_normalized_name", "subjects", type_="unique")
    op.drop_column("subjects", "normalized_code")
    op.drop_column("subjects", "normalized_name")
