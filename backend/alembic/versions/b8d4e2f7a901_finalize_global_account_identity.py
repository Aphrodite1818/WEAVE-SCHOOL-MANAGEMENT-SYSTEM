"""Finalize global account identity types and remove legacy teacher storage.

Revision ID: b8d4e2f7a901
Revises: 6a7c9d2e1f30
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8d4e2f7a901"
down_revision: Union[str, Sequence[str], None] = "6a7c9d2e1f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist explicit global-account actor types and remove legacy storage."""

    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE public.actor_type "
            "ADD VALUE IF NOT EXISTS 'teacher_account'"
        )
        op.execute(
            "ALTER TYPE public.actor_type "
            "ADD VALUE IF NOT EXISTS 'parent_account'"
        )

    op.execute(
        sa.text(
            """
            UPDATE public.auth_identities
            SET actor_type = 'teacher_account'::public.actor_type
            WHERE actor_type = 'teacher'::public.actor_type
              AND tenant_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE public.auth_identities
            SET actor_type = 'parent_account'::public.actor_type
            WHERE actor_type = 'parent'::public.actor_type
              AND tenant_id IS NULL
            """
        )
    )
    op.execute(sa.text("DROP TABLE IF EXISTS public.legacy_teachers CASCADE"))


def downgrade() -> None:
    """Downgrade cannot remove PostgreSQL enum values safely."""

    raise RuntimeError(
        "This migration is intentionally irreversible. Restore a pre-migration "
        "database backup when reverting the global account refactor."
    )
