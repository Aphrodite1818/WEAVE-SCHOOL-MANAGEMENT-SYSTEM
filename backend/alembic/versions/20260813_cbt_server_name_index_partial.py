"""make the CBT server name index partial

Revision ID: 20260813_cbt_name_partial
Revises: 20260813_cbt_name_unique
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_cbt_name_partial"
down_revision = "20260813_cbt_name_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "uq_cbt_servers_tenant_normalized_name",
        table_name="cbt_servers",
        schema="public",
    )
    op.create_index(
        "uq_cbt_servers_tenant_normalized_name",
        "cbt_servers",
        [
            "tenant_id",
            sa.text("lower(regexp_replace(btrim(name), '\\s+', ' ', 'g'))"),
        ],
        unique=True,
        schema="public",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_cbt_servers_tenant_normalized_name",
        table_name="cbt_servers",
        schema="public",
    )
    op.create_index(
        "uq_cbt_servers_tenant_normalized_name",
        "cbt_servers",
        [
            "tenant_id",
            sa.text("lower(regexp_replace(btrim(name), '\\s+', ' ', 'g'))"),
        ],
        unique=True,
        schema="public",
    )
