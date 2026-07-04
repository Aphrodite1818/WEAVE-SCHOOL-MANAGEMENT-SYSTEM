"""add subscription billing tables

Revision ID: 20260704_subscription_billing
Revises: 20260703_merge_acad_heads
Create Date: 2026-07-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260704_subscription_billing"
down_revision = "20260703_merge_acad_heads"
branch_labels = None
depends_on = None

PUBLIC_SCHEMA = "public"

subscription_plan_enum = postgresql.ENUM(
    "free_trial",
    "plus",
    "professional",
    "enterprise",
    name="subscriptionplan",
    schema=PUBLIC_SCHEMA,
    # create_type=False prevents SQLAlchemy from auto-issuing CREATE TYPE /
    # DROP TYPE as a side effect of op.create_table()/op.drop_table() below
    # (which would otherwise run with checkfirst=False right after our
    # explicit .create() call in upgrade(), causing a duplicate-type error).
    # We manage this type's lifecycle explicitly via .create()/.drop().
    create_type=False,
)
# All enums below are created explicitly via .create(bind, checkfirst=True)
# in upgrade() and dropped explicitly via .drop(bind, checkfirst=True) in
# downgrade(). create_type=False on every one of them is required so that
# op.create_table()/op.drop_table() do NOT also try to auto-create/drop
# these types as a side effect of using them as column types -- that
# automatic path runs with checkfirst=False and would collide with our
# explicit .create() call, raising "type already exists".
subscription_status_enum = postgresql.ENUM(
    "trialing",
    "active",
    "non_renewing",
    "past_due",
    "grace_period",
    "expired",
    "cancelled",
    name="subscription_status",
    schema=PUBLIC_SCHEMA,
    create_type=False,
)
billing_interval_enum = postgresql.ENUM(
    "monthly",
    name="billing_interval",
    schema=PUBLIC_SCHEMA,
    create_type=False,
)
payment_provider_enum = postgresql.ENUM(
    "paystack",
    "manual",
    name="payment_provider",
    schema=PUBLIC_SCHEMA,
    create_type=False,
)
payment_status_enum = postgresql.ENUM(
    "pending",
    "success",
    "failed",
    "abandoned",
    name="payment_status",
    schema=PUBLIC_SCHEMA,
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    # If the main table already exists in the target DB, assume this
    # migration (or an equivalent manual change) has already been applied
    # and skip creating objects to avoid DuplicateTableError.
    inspector = sa.inspect(bind)
    if "tenant_subscriptions" in inspector.get_table_names(schema=PUBLIC_SCHEMA):
        return

    # subscription_plan_enum uses create_type=False (see its declaration
    # above) so it is NOT auto-created by op.create_table() below. Nothing
    # earlier in the migration history creates "subscriptionplan" either, so
    # we must create it explicitly here. checkfirst=True keeps this safe if
    # it already exists in some environment.
    subscription_plan_enum.create(bind, checkfirst=True)
    subscription_status_enum.create(bind, checkfirst=True)
    billing_interval_enum.create(bind, checkfirst=True)
    payment_provider_enum.create(bind, checkfirst=True)
    payment_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "tenant_subscriptions",
        sa.Column("plan_code", subscription_plan_enum, nullable=False),
        sa.Column("status", subscription_status_enum, nullable=False),
        sa.Column("billing_interval", billing_interval_enum, nullable=False),
        sa.Column(
            "provider",
            payment_provider_enum,
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("provider_customer_code", sa.String(length=120), nullable=True),
        sa.Column("provider_subscription_code", sa.String(length=120), nullable=True),
        sa.Column("provider_email_token", sa.String(length=255), nullable=True),
        sa.Column("last_payment_reference", sa.String(length=120), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{PUBLIC_SCHEMA}.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_tenant_subscriptions_tenant_current",
        "tenant_subscriptions",
        ["tenant_id", "is_current"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "uq_tenant_subscriptions_current_per_tenant",
        "tenant_subscriptions",
        ["tenant_id"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_tenant_subscriptions_status_period_end",
        "tenant_subscriptions",
        ["status", "current_period_end"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_tenant_subscriptions_status_grace_ends_at",
        "tenant_subscriptions",
        ["status", "grace_ends_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "uq_tenant_subscriptions_provider_subscription_code",
        "tenant_subscriptions",
        ["provider", "provider_subscription_code"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("provider_subscription_code IS NOT NULL"),
    )

    op.create_table(
        "payment_transactions",
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", payment_provider_enum, nullable=False),
        sa.Column(
            "status",
            payment_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reference", sa.String(length=120), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=120), nullable=True),
        sa.Column("plan_code", subscription_plan_enum, nullable=False),
        sa.Column("billing_interval", billing_interval_enum, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_kobo", sa.Integer(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'NGN'"),
        ),
        sa.Column("authorization_url", sa.Text(), nullable=True),
        sa.Column("access_code", sa.String(length=120), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["subscription_id"], [f"{PUBLIC_SCHEMA}.tenant_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{PUBLIC_SCHEMA}.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_payment_transactions_tenant_status",
        "payment_transactions",
        ["tenant_id", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_payment_transactions_tenant_subscription",
        "payment_transactions",
        ["tenant_id", "subscription_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("provider", payment_provider_enum, nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "event_type",
            "event_key",
            name="uq_payment_webhook_events_provider_type_key",
        ),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_payment_webhook_events_provider_type",
        "payment_webhook_events",
        ["provider", "event_type"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_webhook_events_provider_type",
        table_name="payment_webhook_events",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("payment_webhook_events", schema=PUBLIC_SCHEMA)

    op.drop_index(
        "ix_payment_transactions_tenant_subscription",
        table_name="payment_transactions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_payment_transactions_tenant_status",
        table_name="payment_transactions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("payment_transactions", schema=PUBLIC_SCHEMA)

    op.drop_index(
        "uq_tenant_subscriptions_provider_subscription_code",
        table_name="tenant_subscriptions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_tenant_subscriptions_status_grace_ends_at",
        table_name="tenant_subscriptions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_tenant_subscriptions_status_period_end",
        table_name="tenant_subscriptions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "uq_tenant_subscriptions_current_per_tenant",
        table_name="tenant_subscriptions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_tenant_subscriptions_tenant_current",
        table_name="tenant_subscriptions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("tenant_subscriptions", schema=PUBLIC_SCHEMA)

    bind = op.get_bind()
    payment_status_enum.drop(bind, checkfirst=True)
    payment_provider_enum.drop(bind, checkfirst=True)
    billing_interval_enum.drop(bind, checkfirst=True)
    subscription_status_enum.drop(bind, checkfirst=True)
    # subscription_plan_enum is now created by this migration, so it must
    # also be dropped here on downgrade (previously omitted, since the
    # migration assumed the type was owned/managed elsewhere).
    subscription_plan_enum.drop(bind, checkfirst=True)
