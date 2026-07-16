"""Repoint migrated email identities to global account owners.

Revision ID: c4e7a9b2d610
Revises: b8d4e2f7a901
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4e7a9b2d610"
down_revision: Union[str, Sequence[str], None] = "b8d4e2f7a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make each parent/teacher email identity own the global account row."""

    op.execute(
        sa.text(
            """
            UPDATE public.auth_identities AS identity
            SET actor_type = 'parent_account'::public.actor_type,
                actor_id = account.id,
                tenant_id = NULL,
                is_active = account.is_active
            FROM public.parent_accounts AS account
            WHERE identity.identifier_type = 'email'::public.identifier_type
              AND lower(trim(identity.identifier)) = lower(trim(account.email))
              AND identity.actor_type IN (
                    'parent'::public.actor_type,
                    'parent_account'::public.actor_type
              )
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE public.auth_identities AS identity
            SET actor_type = 'teacher_account'::public.actor_type,
                actor_id = account.id,
                tenant_id = NULL,
                is_active = account.is_active
            FROM public.teacher_accounts AS account
            WHERE identity.identifier_type = 'email'::public.identifier_type
              AND lower(trim(identity.identifier)) = lower(trim(account.email))
              AND identity.actor_type IN (
                    'teacher'::public.actor_type,
                    'teacher_account'::public.actor_type
              )
            """
        )
    )

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM public.auth_identities
                    WHERE identifier_type = 'email'::public.identifier_type
                      AND actor_type IN (
                            'parent'::public.actor_type,
                            'teacher'::public.actor_type
                      )
                ) THEN
                    RAISE EXCEPTION
                        'Legacy parent/teacher email identities remain after account migration';
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    """Global account ownership cannot be reversed without tenant selection."""

    raise RuntimeError(
        "This identity migration is intentionally irreversible because one "
        "global account may now own memberships in multiple tenants."
    )
