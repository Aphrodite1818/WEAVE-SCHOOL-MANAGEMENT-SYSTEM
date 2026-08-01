"""Version the universal tenant-branding dark foundation.

Revision ID: 20260801_branding_dark
Revises: 20260801_branding_palettes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_branding_dark"
down_revision: str | Sequence[str] | None = "20260801_branding_palettes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_branding"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(TABLE)}


def upgrade() -> None:
    if "token_schema_version" not in _columns():
        return
    op.execute(sa.text(f"UPDATE {TABLE} SET token_schema_version = 4"))
    op.alter_column(TABLE, "token_schema_version", server_default="4")


def downgrade() -> None:
    if "token_schema_version" not in _columns():
        return
    op.execute(sa.text(f"UPDATE {TABLE} SET token_schema_version = 2"))
    op.alter_column(TABLE, "token_schema_version", server_default="2")
