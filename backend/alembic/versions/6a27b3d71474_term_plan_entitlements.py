"""term plan entitlements

Revision ID: 6a27b3d71474
Revises: c69b126b7394
Create Date: 2026-08-11 20:35:39
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6a27b3d71474"
down_revision: Union[str, Sequence[str], None] = "c69b126b7394"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE public.subscriptionplan ADD VALUE IF NOT EXISTS 'free'")
        op.execute("ALTER TYPE public.billing_interval ADD VALUE IF NOT EXISTS 'term'")
        op.execute("ALTER TYPE public.billing_interval ADD VALUE IF NOT EXISTS 'trial'")
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE public.term_entitlement_status AS ENUM
                ('pending', 'active', 'closed', 'expired', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    subscription_plan = postgresql.ENUM(
        "free_trial",
        "free",
        "plus",
        "professional",
        "enterprise",
        name="subscriptionplan",
        schema="public",
        create_type=False,
    )
    payment_provider = postgresql.ENUM(
        "paystack",
        "manual",
        name="payment_provider",
        schema="public",
        create_type=False,
    )
    entitlement_status = postgresql.ENUM(
        "pending",
        "active",
        "closed",
        "expired",
        "failed",
        name="term_entitlement_status",
        schema="public",
        create_type=False,
    )

    # Recurring purchases cannot be attached safely to a term. They are obsolete
    # checkout artifacts, not valid term entitlements, so remove them explicitly.
    op.execute("DELETE FROM public.payment_transactions")
    op.drop_index(
        "ix_payment_transactions_tenant_subscription",
        table_name="payment_transactions",
        schema="public",
    )
    op.drop_constraint(
        "payment_transactions_subscription_id_fkey",
        "payment_transactions",
        schema="public",
        type_="foreignkey",
    )
    op.drop_column("payment_transactions", "subscription_id", schema="public")
    op.add_column(
        "payment_transactions",
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        schema="public",
    )
    op.create_foreign_key(
        "fk_payment_transactions_academic_term",
        "payment_transactions",
        "academic_terms",
        ["academic_term_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_payment_transactions_tenant_term",
        "payment_transactions",
        ["tenant_id", "academic_term_id"],
        schema="public",
    )
    op.add_column(
        "tenants",
        sa.Column("initial_plan_intent", subscription_plan, nullable=True),
        schema="public",
    )
    op.execute("""
        UPDATE public.tenants
        SET initial_plan_intent = NULLIF(feature_flags ->> 'registration_selected_plan_code', '')::public.subscriptionplan
        WHERE feature_flags ? 'registration_selected_plan_code'
    """)

    op.execute("DELETE FROM public.tenant_subscriptions WHERE plan_code <> 'free_trial'")
    op.execute(
        "UPDATE public.tenant_subscriptions SET billing_interval = 'trial' "
        "WHERE plan_code = 'free_trial'"
    )
    op.drop_index(
        "ix_tenant_subscriptions_status_grace_ends_at",
        table_name="tenant_subscriptions",
        schema="public",
    )
    op.drop_index(
        "ix_tenant_subscriptions_status_period_end",
        table_name="tenant_subscriptions",
        schema="public",
    )
    op.drop_index(
        "uq_tenant_subscriptions_provider_subscription_code",
        table_name="tenant_subscriptions",
        schema="public",
    )
    for column_name in (
        "grace_ends_at",
        "cancel_at_period_end",
        "cancelled_at",
        "provider_customer_code",
        "provider_subscription_code",
        "provider_email_token",
        "last_payment_reference",
        "last_payment_at",
        "next_payment_at",
    ):
        op.drop_column("tenant_subscriptions", column_name, schema="public")
    op.create_index(
        "ix_tenant_subscriptions_trial_expiry",
        "tenant_subscriptions",
        ["status", "trial_ends_at"],
        schema="public",
    )

    op.drop_table("subscription_plan_changes", schema="public")

    op.create_table(
        "term_plan_entitlements",
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        sa.Column("plan_code", subscription_plan, nullable=False),
        sa.Column("status", entitlement_status, server_default="pending", nullable=False),
        sa.Column("payment_transaction_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(10), server_default="NGN", nullable=False),
        sa.Column("provider", payment_provider, server_default="manual", nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safety_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.String(120), nullable=True),
        sa.Column("activated_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["public.payment_transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_term_entitlements_tenant_term",
        "term_plan_entitlements",
        ["tenant_id", "academic_term_id"],
        schema="public",
    )
    op.create_index(
        "uq_term_entitlements_active_term",
        "term_plan_entitlements",
        ["tenant_id", "academic_term_id"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    subscription_plan = postgresql.ENUM(
        "free_trial",
        "free",
        "plus",
        "professional",
        "enterprise",
        name="subscriptionplan",
        schema="public",
        create_type=False,
    )
    change_type = postgresql.ENUM(
        "upgrade",
        "downgrade",
        name="subscription_plan_change_type",
        schema="public",
        create_type=False,
    )
    change_status = postgresql.ENUM(
        "pending",
        "blocked",
        "scheduled",
        "awaiting_payment",
        "applied",
        "cancelled",
        "failed",
        name="subscription_plan_change_status",
        schema="public",
        create_type=False,
    )
    op.create_table(
        "subscription_plan_changes",
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        sa.Column("current_plan_code", subscription_plan, nullable=False),
        sa.Column("target_plan_code", subscription_plan, nullable=False),
        sa.Column("change_type", change_type, nullable=False),
        sa.Column("status", change_status, nullable=False),
        sa.Column("requested_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("blockers_json", postgresql.JSONB(), nullable=True),
        sa.Column("provider_reference", sa.String(120), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["public.tenant_subscriptions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.drop_index(
        "ix_tenant_subscriptions_trial_expiry", table_name="tenant_subscriptions", schema="public"
    )
    legacy_columns = (
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_customer_code", sa.String(120), nullable=True),
        sa.Column("provider_subscription_code", sa.String(120), nullable=True),
        sa.Column("provider_email_token", sa.String(255), nullable=True),
        sa.Column("last_payment_reference", sa.String(120), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_payment_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in legacy_columns:
        op.add_column("tenant_subscriptions", column, schema="public")
    op.create_index(
        "ix_tenant_subscriptions_status_grace_ends_at",
        "tenant_subscriptions",
        ["status", "grace_ends_at"],
        schema="public",
    )
    op.create_index(
        "ix_tenant_subscriptions_status_period_end",
        "tenant_subscriptions",
        ["status", "current_period_end"],
        schema="public",
    )
    op.create_index(
        "uq_tenant_subscriptions_provider_subscription_code",
        "tenant_subscriptions",
        ["provider", "provider_subscription_code"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("provider_subscription_code IS NOT NULL"),
    )

    op.drop_index(
        "uq_term_entitlements_active_term", table_name="term_plan_entitlements", schema="public"
    )
    op.drop_index(
        "ix_term_entitlements_tenant_term", table_name="term_plan_entitlements", schema="public"
    )
    op.drop_table("term_plan_entitlements", schema="public")
    op.drop_column("tenants", "initial_plan_intent", schema="public")
    op.drop_constraint(
        "fk_payment_transactions_academic_term",
        "payment_transactions",
        schema="public",
        type_="foreignkey",
    )
    op.execute("DROP INDEX IF EXISTS public.ix_payment_transactions_tenant_term")
    op.drop_column("payment_transactions", "academic_term_id", schema="public")
    op.add_column(
        "payment_transactions",
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        schema="public",
    )
    op.create_foreign_key(
        "payment_transactions_subscription_id_fkey",
        "payment_transactions",
        "tenant_subscriptions",
        ["subscription_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
    )
    op.create_index(
        "ix_payment_transactions_tenant_subscription",
        "payment_transactions",
        ["tenant_id", "subscription_id"],
        schema="public",
    )
    op.execute("DROP TYPE IF EXISTS public.term_entitlement_status")
    # PostgreSQL enum values are intentionally retained because removing enum values
    # requires rebuilding every dependent column and can destroy unrelated history.
