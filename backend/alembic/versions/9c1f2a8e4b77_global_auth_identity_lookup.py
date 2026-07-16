"""Allow global auth identities for parent and teacher accounts.

Revision ID: 9c1f2a8e4b77
Revises: 7b2f6c9d4e10
Create Date: 2026-07-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9c1f2a8e4b77"
down_revision = "7b2f6c9d4e10"
branch_labels = None
depends_on = None

PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    """Make auth identity tenant scope optional for global accounts."""

    op.alter_column(
        "auth_identities",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=True,
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    """Restore mandatory tenant scope only when no global identities exist."""

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM public.auth_identities
                    WHERE tenant_id IS NULL
                ) THEN
                    RAISE EXCEPTION
                        'Cannot make auth_identities.tenant_id NOT NULL while global identities exist';
                END IF;
            END
            $$;
            """
        )
    )

    op.alter_column(
        "auth_identities",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema=PUBLIC_SCHEMA,
    )
