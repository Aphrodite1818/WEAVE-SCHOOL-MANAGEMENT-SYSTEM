"""Add persistent per-actor product guide state.

Revision ID: 20260801_user_guides
Revises: 20260731_subscription_changes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260801_user_guides"
down_revision: str | Sequence[str] | None = "20260731_subscription_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(bind: sa.Connection) -> bool:
    return "user_guide_states" in sa.inspect(bind).get_table_names(schema="public")


def upgrade() -> None:
    bind = op.get_bind()

    # The dynamic clean baseline may already have created this model on a fresh
    # database. Existing databases at the previous revision still need the DDL.
    if _table_exists(bind):
        return

    op.create_table(
        "user_guide_states",
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope_key", sa.String(length=40), server_default="global", nullable=False),
        sa.Column("guide_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="not_started", nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column(
            "skipped_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("remind_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'dismissed', 'completed')",
            name="ck_user_guide_states_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "actor_type",
            "actor_id",
            "scope_key",
            "guide_key",
            name="uq_user_guide_states_actor_scope_guide",
        ),
        schema="public",
    )
    op.create_index(
        "ix_user_guide_states_actor_scope",
        "user_guide_states",
        ["actor_type", "actor_id", "scope_key"],
        schema="public",
    )
    op.create_index(
        op.f("ix_public_user_guide_states_tenant_id"),
        "user_guide_states",
        ["tenant_id"],
        schema="public",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return

    op.drop_index(
        op.f("ix_public_user_guide_states_tenant_id"),
        table_name="user_guide_states",
        schema="public",
    )
    op.drop_index(
        "ix_user_guide_states_actor_scope",
        table_name="user_guide_states",
        schema="public",
    )
    op.drop_table("user_guide_states", schema="public")
