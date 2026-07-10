"""add security ip blocks

Revision ID: 20260710_add_security_ip_blocks
Revises: 20260710_add_platform_controls
Create Date: 2026-07-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_add_security_ip_blocks"
down_revision = "20260710_add_platform_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_ip_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address_hash", sa.String(length=255), nullable=False),
        sa.Column("ip_address_label", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("blocked_by_superadmin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unblocked_by_superadmin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unblocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unblock_reason", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["blocked_by_superadmin_id"],
            ["public.superadmins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["unblocked_by_superadmin_id"],
            ["public.superadmins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index("ix_security_ip_blocks_ip_address_hash", "security_ip_blocks", ["ip_address_hash"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_blocked_by_superadmin_id", "security_ip_blocks", ["blocked_by_superadmin_id"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_unblocked_by_superadmin_id", "security_ip_blocks", ["unblocked_by_superadmin_id"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_blocked_at", "security_ip_blocks", ["blocked_at"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_expires_at", "security_ip_blocks", ["expires_at"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_unblocked_at", "security_ip_blocks", ["unblocked_at"], unique=False, schema="public")
    op.create_index("ix_security_ip_blocks_is_active", "security_ip_blocks", ["is_active"], unique=False, schema="public")
    op.create_index(
        "ix_security_ip_blocks_active_hash",
        "security_ip_blocks",
        ["ip_address_hash", "is_active", "expires_at"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index("ix_security_ip_blocks_active_hash", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_is_active", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_unblocked_at", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_expires_at", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_blocked_at", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_unblocked_by_superadmin_id", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_blocked_by_superadmin_id", table_name="security_ip_blocks", schema="public")
    op.drop_index("ix_security_ip_blocks_ip_address_hash", table_name="security_ip_blocks", schema="public")
    op.drop_table("security_ip_blocks", schema="public")
