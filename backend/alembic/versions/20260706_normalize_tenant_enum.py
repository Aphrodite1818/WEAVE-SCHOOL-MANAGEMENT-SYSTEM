"""normalize legacy tenant enum values

Revision ID: 20260706_normalize_tenant_enum_values
Revises: 20260705_add_users_is_verified
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "20260706_normalize_tenant_enum"
down_revision = "20260705_add_users_is_verified"
branch_labels = None
depends_on = None


RENAME_ENUM_VALUES_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'FREE_TRIAL'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'free_trial'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'FREE_TRIAL' TO 'free_trial';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'PLUS'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'plus'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'PLUS' TO 'plus';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'PROFESSIONAL'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'professional'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'PROFESSIONAL' TO 'professional';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'ENTERPRISE'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'subscriptionplan'
          AND e.enumlabel = 'enterprise'
    ) THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'ENTERPRISE' TO 'enterprise';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'ACTIVE'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'active'
    ) THEN
        ALTER TYPE public.tenantstatus RENAME VALUE 'ACTIVE' TO 'active';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'INACTIVE'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'inactive'
    ) THEN
        ALTER TYPE public.tenantstatus RENAME VALUE 'INACTIVE' TO 'inactive';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'SUSPENDED'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'suspended'
    ) THEN
        ALTER TYPE public.tenantstatus RENAME VALUE 'SUSPENDED' TO 'suspended';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'TRIAL'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'trial'
    ) THEN
        ALTER TYPE public.tenantstatus RENAME VALUE 'TRIAL' TO 'trial';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'EXPIRED'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantstatus'
          AND e.enumlabel = 'expired'
    ) THEN
        ALTER TYPE public.tenantstatus RENAME VALUE 'EXPIRED' TO 'expired';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'PENDING_VERIFICATION'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'pending_verification'
    ) THEN
        ALTER TYPE public.tenantverificationstatus RENAME VALUE 'PENDING_VERIFICATION' TO 'pending_verification';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'ACTIVE'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'active'
    ) THEN
        ALTER TYPE public.tenantverificationstatus RENAME VALUE 'ACTIVE' TO 'active';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'REJECTED'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE n.nspname = 'public'
          AND t.typname = 'tenantverificationstatus'
          AND e.enumlabel = 'rejected'
    ) THEN
        ALTER TYPE public.tenantverificationstatus RENAME VALUE 'REJECTED' TO 'rejected';
    END IF;
END $$;
"""


DOWNGRADE_ENUM_VALUES_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'free_trial')
       AND NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'FREE_TRIAL') THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'free_trial' TO 'FREE_TRIAL';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'plus')
       AND NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'PLUS') THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'plus' TO 'PLUS';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'professional')
       AND NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'PROFESSIONAL') THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'professional' TO 'PROFESSIONAL';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'enterprise')
       AND NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_enum e ON e.enumtypid = t.oid WHERE n.nspname = 'public' AND t.typname = 'subscriptionplan' AND e.enumlabel = 'ENTERPRISE') THEN
        ALTER TYPE public.subscriptionplan RENAME VALUE 'enterprise' TO 'ENTERPRISE';
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(RENAME_ENUM_VALUES_SQL)


def downgrade() -> None:
    # Downgrade only the subscription plan enum because newer application code
    # depends on lowercase tenant status / verification values. Full rollback of
    # all enum labels should be done only with the matching old application code.
    op.execute(DOWNGRADE_ENUM_VALUES_SQL)
