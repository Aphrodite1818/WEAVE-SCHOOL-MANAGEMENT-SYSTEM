"""enforce tenant-scoped cbt server name uniqueness

Revision ID: 20260813_cbt_name_unique
Revises: 20260813_cbt_tables
Create Date: 2026-08-13 18:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_cbt_name_unique"
down_revision: Union[str, Sequence[str], None] = "20260813_cbt_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        sa.text(
            f"""
            UPDATE {PUBLIC_SCHEMA}.cbt_servers
            SET name = regexp_replace(btrim(name), '\\s+', ' ', 'g')
            WHERE name <> regexp_replace(btrim(name), '\\s+', ' ', 'g')
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM (
                        SELECT
                            tenant_id,
                            lower(regexp_replace(btrim(name), '\\s+', ' ', 'g')) AS normalized_name,
                            COUNT(*) AS match_count
                        FROM {PUBLIC_SCHEMA}.cbt_servers
                        WHERE revoked_at IS NULL
                        GROUP BY tenant_id, lower(regexp_replace(btrim(name), '\\s+', ' ', 'g'))
                        HAVING COUNT(*) > 1
                    ) duplicates
                ) THEN
                    RAISE EXCEPTION
                        'Cannot enforce unique normalized CBT server names: duplicate active names already exist within the same tenant.';
                END IF;
            END $$;
            """
        )
    )
    op.create_index(
        "uq_cbt_servers_tenant_normalized_name",
        "cbt_servers",
        [
            "tenant_id",
            sa.text("lower(regexp_replace(btrim(name), '\\s+', ' ', 'g'))"),
        ],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "uq_cbt_servers_tenant_normalized_name",
        table_name="cbt_servers",
        schema=PUBLIC_SCHEMA,
    )
