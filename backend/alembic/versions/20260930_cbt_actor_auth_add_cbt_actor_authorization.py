"""add CBT actor authorization

Revision ID: 20260930_cbt_actor_auth
Revises: 20260930_cbt_ai_quota
Create Date: 2026-09-30 19:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_cbt_actor_auth"
down_revision: Union[str, Sequence[str], None] = "20260930_cbt_ai_quota"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cbt_actor_authorizations",
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("teacher_account_id", sa.UUID(), nullable=True),
        sa.Column("teacher_membership_id", sa.UUID(), nullable=True),
        sa.Column("tenant_admin_id", sa.UUID(), nullable=True),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=255), nullable=True),
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
        sa.CheckConstraint(
            """
            (
                role = 'teacher'
                AND teacher_account_id IS NOT NULL
                AND teacher_membership_id IS NOT NULL
                AND tenant_admin_id IS NULL
            )
            OR
            (
                role = 'admin'
                AND teacher_account_id IS NULL
                AND teacher_membership_id IS NULL
                AND tenant_admin_id IS NOT NULL
            )
            """,
            name="ck_cbt_actor_authorizations_actor_consistency",
        ),
        sa.CheckConstraint(
            "access_token_expires_at <= absolute_expires_at",
            name="ck_cbt_actor_authorizations_access_within_absolute_expiry",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_cbt_actor_authorizations_valid_revocation",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_account_id"],
            ["public.teacher_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_membership_id"],
            ["public.teacher_memberships.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_admin_id"],
            ["public.tenant_admins.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_cbt_actor_authorizations_tenant_role",
        "cbt_actor_authorizations",
        ["tenant_id", "role"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_actor_authorizations_teacher_membership_revoked",
        "cbt_actor_authorizations",
        ["teacher_membership_id", "revoked_at"],
        unique=False,
        schema="public",
        postgresql_where=sa.text("teacher_membership_id IS NOT NULL"),
    )
    op.create_index(
        "ix_cbt_actor_authorizations_teacher_account_revoked",
        "cbt_actor_authorizations",
        ["teacher_account_id", "revoked_at"],
        unique=False,
        schema="public",
        postgresql_where=sa.text("teacher_account_id IS NOT NULL"),
    )
    op.create_index(
        "ix_cbt_actor_authorizations_admin_revoked",
        "cbt_actor_authorizations",
        ["tenant_admin_id", "revoked_at"],
        unique=False,
        schema="public",
        postgresql_where=sa.text("tenant_admin_id IS NOT NULL"),
    )
    op.create_index(
        "ix_cbt_actor_authorizations_absolute_expiry",
        "cbt_actor_authorizations",
        ["absolute_expires_at"],
        unique=False,
        schema="public",
    )

    op.create_table(
        "cbt_actor_refresh_tokens",
        sa.Column("authorization_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_cbt_actor_refresh_tokens_valid_expiry",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_consumed_at",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_revocation",
        ),
        sa.CheckConstraint(
            "reuse_detected_at IS NULL OR reuse_detected_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_reuse",
        ),
        sa.CheckConstraint(
            "replaced_by_token_id IS NULL OR replaced_by_token_id <> id",
            name="ck_cbt_actor_refresh_tokens_not_self_replaced",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_id"],
            ["public.cbt_actor_authorizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_token_id"],
            ["public.cbt_actor_refresh_tokens.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema="public",
    )
    op.create_index(
        "ix_cbt_actor_refresh_tokens_authorization_id",
        "cbt_actor_refresh_tokens",
        ["authorization_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_actor_refresh_tokens_authorization_expiry",
        "cbt_actor_refresh_tokens",
        ["authorization_id", "expires_at"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_actor_refresh_tokens_authorization_consumed",
        "cbt_actor_refresh_tokens",
        ["authorization_id", "consumed_at"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cbt_actor_refresh_tokens_authorization_consumed",
        table_name="cbt_actor_refresh_tokens",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_refresh_tokens_authorization_expiry",
        table_name="cbt_actor_refresh_tokens",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_refresh_tokens_authorization_id",
        table_name="cbt_actor_refresh_tokens",
        schema="public",
    )
    op.drop_table("cbt_actor_refresh_tokens", schema="public")

    op.drop_index(
        "ix_cbt_actor_authorizations_absolute_expiry",
        table_name="cbt_actor_authorizations",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_authorizations_admin_revoked",
        table_name="cbt_actor_authorizations",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_authorizations_teacher_account_revoked",
        table_name="cbt_actor_authorizations",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_authorizations_teacher_membership_revoked",
        table_name="cbt_actor_authorizations",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_actor_authorizations_tenant_role",
        table_name="cbt_actor_authorizations",
        schema="public",
    )
    op.drop_table("cbt_actor_authorizations", schema="public")
