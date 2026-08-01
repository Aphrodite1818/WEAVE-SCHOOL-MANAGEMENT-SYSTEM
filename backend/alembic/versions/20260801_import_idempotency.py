"""Prevent duplicate confirmed bulk imports.

Revision ID: 20260801_import_idempotency
Revises: 20260731_clean_baseline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_import_idempotency"
down_revision: str | Sequence[str] | None = "20260731_clean_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind: sa.Connection) -> set[str]:
    inspector = sa.inspect(bind)
    if "import_jobs" not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns("import_jobs", schema="public")}


def _index_names(bind: sa.Connection) -> set[str]:
    inspector = sa.inspect(bind)
    if "import_jobs" not in inspector.get_table_names(schema="public"):
        return set()
    return {index["name"] for index in inspector.get_indexes("import_jobs", schema="public")}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind)
    if not columns:
        return

    if "source_fingerprint" not in columns:
        op.add_column(
            "import_jobs",
            sa.Column("source_fingerprint", sa.String(length=64), nullable=True),
            schema="public",
        )
    if "confirmed_fingerprint" not in columns:
        op.add_column(
            "import_jobs",
            sa.Column("confirmed_fingerprint", sa.String(length=64), nullable=True),
            schema="public",
        )

    indexes = _index_names(bind)
    if "ix_import_jobs_tenant_source_fingerprint" not in indexes:
        op.create_index(
            "ix_import_jobs_tenant_source_fingerprint",
            "import_jobs",
            ["tenant_id", "resource_type", "source_fingerprint"],
            schema="public",
        )
    if "uq_import_jobs_tenant_confirmed_fingerprint" not in indexes:
        op.create_index(
            "uq_import_jobs_tenant_confirmed_fingerprint",
            "import_jobs",
            ["tenant_id", "resource_type", "confirmed_fingerprint"],
            unique=True,
            schema="public",
            postgresql_where=sa.text("confirmed_fingerprint IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = _index_names(bind)
    if "uq_import_jobs_tenant_confirmed_fingerprint" in indexes:
        op.drop_index(
            "uq_import_jobs_tenant_confirmed_fingerprint",
            table_name="import_jobs",
            schema="public",
        )
    if "ix_import_jobs_tenant_source_fingerprint" in indexes:
        op.drop_index(
            "ix_import_jobs_tenant_source_fingerprint",
            table_name="import_jobs",
            schema="public",
        )

    columns = _column_names(bind)
    if "confirmed_fingerprint" in columns:
        op.drop_column("import_jobs", "confirmed_fingerprint", schema="public")
    if "source_fingerprint" in columns:
        op.drop_column("import_jobs", "source_fingerprint", schema="public")
