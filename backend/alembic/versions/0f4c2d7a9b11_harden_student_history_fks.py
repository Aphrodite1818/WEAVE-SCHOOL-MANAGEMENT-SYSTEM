"""Harden student history foreign keys and membership lifecycle checks.

Revision ID: 0f4c2d7a9b11
Revises: e99b2f5e17b2
Create Date: 2026-07-15
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0f4c2d7a9b11"
down_revision: Union[str, Sequence[str], None] = "e99b2f5e17b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    """Protect lifecycle and historical records from accidental deletion."""

    # Backfill legacy inactive memberships before enforcing the stricter
    # lifecycle invariant.
    op.execute(
        sa.text(
            """
            UPDATE public.parent_memberships
            SET ended_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE status = 'inactive'
              AND ended_at IS NULL
            """
        )
    )

    op.drop_constraint(
        "ck_parent_membership_status_end_consistency",
        "parent_memberships",
        schema=PUBLIC_SCHEMA,
        type_="check",
    )
    op.create_check_constraint(
        "ck_parent_membership_status_end_consistency",
        "parent_memberships",
        """
        (
            status IN ('active', 'read_only')
            AND ended_at IS NULL
        )
        OR
        (
            status = 'inactive'
            AND ended_at IS NOT NULL
        )
        """,
        schema=PUBLIC_SCHEMA,
    )

    op.drop_constraint(
        "student_access_codes_student_id_fkey",
        "student_access_codes",
        schema=PUBLIC_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "student_access_codes_student_id_fkey",
        "student_access_codes",
        "students",
        ["student_id"],
        ["id"],
        source_schema=PUBLIC_SCHEMA,
        referent_schema=PUBLIC_SCHEMA,
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "report_cards_student_id_fkey",
        "report_cards",
        schema=PUBLIC_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "report_cards_student_id_fkey",
        "report_cards",
        "students",
        ["student_id"],
        ["id"],
        source_schema=PUBLIC_SCHEMA,
        referent_schema=PUBLIC_SCHEMA,
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Restore the previous cascade behavior and relaxed membership check."""

    op.drop_constraint(
        "report_cards_student_id_fkey",
        "report_cards",
        schema=PUBLIC_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "report_cards_student_id_fkey",
        "report_cards",
        "students",
        ["student_id"],
        ["id"],
        source_schema=PUBLIC_SCHEMA,
        referent_schema=PUBLIC_SCHEMA,
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "student_access_codes_student_id_fkey",
        "student_access_codes",
        schema=PUBLIC_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "student_access_codes_student_id_fkey",
        "student_access_codes",
        "students",
        ["student_id"],
        ["id"],
        source_schema=PUBLIC_SCHEMA,
        referent_schema=PUBLIC_SCHEMA,
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "ck_parent_membership_status_end_consistency",
        "parent_memberships",
        schema=PUBLIC_SCHEMA,
        type_="check",
    )
    op.create_check_constraint(
        "ck_parent_membership_status_end_consistency",
        "parent_memberships",
        """
        (
            status IN ('active', 'read_only')
            AND ended_at IS NULL
        )
        OR status = 'inactive'
        """,
        schema=PUBLIC_SCHEMA,
    )
