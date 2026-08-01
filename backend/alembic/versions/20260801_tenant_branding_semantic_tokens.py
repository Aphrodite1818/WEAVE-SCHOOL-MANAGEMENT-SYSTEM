"""Add source surface colours and version the tenant-branding token contract.

Revision ID: 20260801_tenant_branding_tokens
Revises: 20260731_clean_baseline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_tenant_branding_tokens"
down_revision: str | Sequence[str] | None = "20260731_clean_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_branding"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(TABLE)}


def upgrade() -> None:
    columns = _columns()
    additions = (
        ("header_color", sa.String(length=7), "#FFFFFF"),
        ("background_color", sa.String(length=7), "#F8FAFC"),
        ("surface_color", sa.String(length=7), "#FFFFFF"),
        # Existing rows start stale so their legacy flat tokens regenerate.
        ("token_schema_version", sa.Integer(), "0"),
    )
    for name, column_type, default in additions:
        if name not in columns:
            op.add_column(
                TABLE,
                sa.Column(name, column_type, nullable=False, server_default=default),
            )
    if "token_schema_version" not in columns:
        op.alter_column(TABLE, "token_schema_version", server_default="1")


def downgrade() -> None:
    columns = _columns()
    for name in ("token_schema_version", "surface_color", "background_color", "header_color"):
        if name in columns:
            op.drop_column(TABLE, name)
