"""Add auditable subscription plan changes.

Revision ID: 20260731_subscription_plan_changes
Revises: 20260731_clean_baseline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260731_subscription_plan_changes"
down_revision: str | Sequence[str] | None = "20260731_clean_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


plan_change_type = postgresql.ENUM(
    "upgrade",
    "downgrade",
    name="subscription_plan_change_type",
    schema="public",
)
plan_change_status = postgresql.ENUM(
    "pending",
    "blocked",
    "scheduled",
    "awaiting_payment",
    "applied",
    "cancelled",
    "failed",
    name="subscription_plan_change_status",
    schema="public",
)


def _table_exists(bind: sa.Connection) -> bool:
    return "subscription_plan_changes" in sa.inspect(bind).get_table_names(
        schema="public"
    )


def upgrade() -> None:
    bind = op.get_bind()
    plan_change_type.create(bind, checkfirst=True)
    plan_change_status.create(bind, checkfirst=True)

    # The clean baseline builds the current SQLAlchemy metadata dynamically. On
    # a fresh database it may therefore have already created this new model.
    # Existing databases stamped at the baseline still need the explicit DDL.
    if _table_exists(bind):
        return

    op.create_table(
        "subscription_plan_changes",
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "current_plan_code",
            sa.Enum(
                "free_trial",
                "plus",
                "professional",
                "enterprise",
                name="subscriptionplan",
                schema="public",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "target_plan_code",
            sa.Enum(
                "free_trial",
                "plus",
                "professional",
                "enterprise",
                name="subscriptionplan",
                schema="public",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "change_type",
            sa.Enum(
                "upgrade",
                "downgrade",
                name="subscription_plan_change_type",
                schema="public",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
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
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("requested_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "usage_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "blockers_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requested_by_admin_id"],
            ["public.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["public.tenant_subscriptions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_subscription_plan_changes_tenant_status",
        "subscription_plan_changes",
        ["tenant_id", "status"],
        schema="public",
    )
    op.create_index(
        "ix_subscription_plan_changes_effective_at",
        "subscription_plan_changes",
        ["status", "effective_at"],
        schema="public",
    )
    op.create_index(
        "uq_subscription_plan_changes_open_per_tenant",
        "subscription_plan_changes",
        ["tenant_id"],
        unique=True,
        schema="public",
        postgresql_where=sa.text(
            "status IN ('pending', 'scheduled', 'awaiting_payment')"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind):
        op.drop_index(
            "uq_subscription_plan_changes_open_per_tenant",
            table_name="subscription_plan_changes",
            schema="public",
        )
        op.drop_index(
            "ix_subscription_plan_changes_effective_at",
            table_name="subscription_plan_changes",
            schema="public",
        )
        op.drop_index(
            "ix_subscription_plan_changes_tenant_status",
            table_name="subscription_plan_changes",
            schema="public",
        )
        op.drop_table("subscription_plan_changes", schema="public")

    plan_change_status.drop(bind, checkfirst=True)
    plan_change_type.drop(bind, checkfirst=True)
