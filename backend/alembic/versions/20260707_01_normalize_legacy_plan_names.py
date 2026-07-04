"""normalize legacy subscription plan names

Revision ID: 20260707_normalize_legacy_plan_names
Revises: 20260706_normalize_tenant_enum_values
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "20260707_normalize_legacy_plan_names"
down_revision = "20260706_normalize_tenant_enum_values"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'free'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'free_trial'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'free' TO 'free_trial';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'starter'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'plus'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'starter' TO 'plus';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'pro'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'professional'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'pro' TO 'professional';
    END IF;
END $$;
"""


DOWNGRADE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'free_trial'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'free'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'free_trial' TO 'free';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'plus'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'starter'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'plus' TO 'starter';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'professional'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'pro'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'professional' TO 'pro';
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
