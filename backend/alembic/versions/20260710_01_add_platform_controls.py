"""add platform controls

Revision ID: 20260710_add_platform_controls
Revises: 20260706_normalize_tenant_enum
Create Date: 2026-07-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_add_platform_controls"
down_revision = "20260706_normalize_tenant_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_controls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lockdown_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("lockdown_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "lockdown_message",
            sa.Text(),
            server_default="LearnlyAI is temporarily in maintenance mode. Please try again later.",
            nullable=False,
        ),
        sa.Column("enabled_by_superadmin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by_superadmin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["enabled_by_superadmin_id"],
            ["public.superadmins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["disabled_by_superadmin_id"],
            ["public.superadmins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_platform_controls_lockdown_enabled",
        "platform_controls",
        ["lockdown_enabled"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_platform_controls_enabled_by_superadmin_id",
        "platform_controls",
        ["enabled_by_superadmin_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_platform_controls_disabled_by_superadmin_id",
        "platform_controls",
        ["disabled_by_superadmin_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_controls_disabled_by_superadmin_id",
        table_name="platform_controls",
        schema="public",
    )
    op.drop_index(
        "ix_platform_controls_enabled_by_superadmin_id",
        table_name="platform_controls",
        schema="public",
    )
    op.drop_index(
        "ix_platform_controls_lockdown_enabled",
        table_name="platform_controls",
        schema="public",
    )
    op.drop_table("platform_controls", schema="public")
