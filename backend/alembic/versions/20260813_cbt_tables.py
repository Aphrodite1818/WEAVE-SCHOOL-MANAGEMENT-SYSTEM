"""add cbt tables

Revision ID: 20260813_cbt_tables
Revises: 20260812_fresh_schema
Create Date: 2026-08-13 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260813_cbt_tables"
down_revision: Union[str, Sequence[str], None] = "20260812_fresh_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_SCHEMA = "public"
cbt_server_status = postgresql.ENUM(
    "active",
    "suspended",
    "revoked",
    name="cbt_server_status",
    schema=PUBLIC_SCHEMA,
)


def upgrade() -> None:
    """Upgrade schema."""

    cbt_server_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cbt_servers",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "suspended",
                "revoked",
                name="cbt_server_status",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("paired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paired_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_version", sa.String(length=50), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ip_address", sa.String(length=45), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["paired_by_admin_id"],
            [f"{PUBLIC_SCHEMA}.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_admin_id"],
            [f"{PUBLIC_SCHEMA}.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{PUBLIC_SCHEMA}.tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_cbt_servers_tenant_last_seen",
        "cbt_servers",
        ["tenant_id", "last_seen_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_cbt_servers_tenant_status",
        "cbt_servers",
        ["tenant_id", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    op.create_table(
        "cbt_server_credentials",
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["server_id"],
            [f"{PUBLIC_SCHEMA}.cbt_servers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_hash"),
        sa.UniqueConstraint("id"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_cbt_server_credentials_server_id",
        "cbt_server_credentials",
        ["server_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_cbt_server_credentials_server_revoked",
        "cbt_server_credentials",
        ["server_id", "revoked_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "uq_cbt_server_credentials_active_server",
        "cbt_server_credentials",
        ["server_id"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "cbt_pairing_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_server_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["created_by_admin_id"],
            [f"{PUBLIC_SCHEMA}.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{PUBLIC_SCHEMA}.tenants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["used_by_server_id"],
            [f"{PUBLIC_SCHEMA}.cbt_servers.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
        sa.UniqueConstraint("id"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_cbt_pairing_codes_tenant_active",
        "cbt_pairing_codes",
        ["tenant_id", "expires_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )
    op.create_index(
        "ix_cbt_pairing_codes_tenant_expiry",
        "cbt_pairing_codes",
        ["tenant_id", "expires_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_cbt_pairing_codes_tenant_expiry",
        table_name="cbt_pairing_codes",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_cbt_pairing_codes_tenant_active",
        table_name="cbt_pairing_codes",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("cbt_pairing_codes", schema=PUBLIC_SCHEMA)

    op.drop_index(
        "uq_cbt_server_credentials_active_server",
        table_name="cbt_server_credentials",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_cbt_server_credentials_server_revoked",
        table_name="cbt_server_credentials",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_cbt_server_credentials_server_id",
        table_name="cbt_server_credentials",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("cbt_server_credentials", schema=PUBLIC_SCHEMA)

    op.drop_index(
        "ix_cbt_servers_tenant_status",
        table_name="cbt_servers",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_cbt_servers_tenant_last_seen",
        table_name="cbt_servers",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_table("cbt_servers", schema=PUBLIC_SCHEMA)

    cbt_server_status.drop(op.get_bind(), checkfirst=True)
