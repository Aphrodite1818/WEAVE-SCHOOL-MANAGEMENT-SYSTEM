"""Allow closing academic terms to remain current.

Revision ID: 20260728_term_closing_current
Revises: 20260728_calendar_revision
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "20260728_term_closing_current"
down_revision: str | Sequence[str] | None = "20260728_calendar_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.academic_terms
        DROP CONSTRAINT IF EXISTS ck_academic_term_current_requires_open
        """
    )
    op.create_check_constraint(
        "ck_academic_term_current_requires_open",
        "academic_terms",
        "is_current = false OR status IN ('open', 'closing')",
        schema="public",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.academic_terms
        SET is_current = false
        WHERE status = 'closing'
          AND is_current = true
        """
    )
    op.drop_constraint(
        "ck_academic_term_current_requires_open",
        "academic_terms",
        schema="public",
        type_="check",
    )
    op.create_check_constraint(
        "ck_academic_term_current_requires_open",
        "academic_terms",
        "is_current = false OR status = 'open'",
        schema="public",
    )
