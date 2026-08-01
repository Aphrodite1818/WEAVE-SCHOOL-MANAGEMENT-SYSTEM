"""Restrict tenant branding to curated palettes.

Revision ID: 20260801_branding_palettes
Revises: 20260801_tenant_branding_tokens
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_branding_palettes"
down_revision: str | Sequence[str] | None = "20260801_tenant_branding_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_branding"
PALETTE_CHECK = "ck_tenant_branding_palette_key"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(TABLE)}


def _check_constraints() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return set()
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(TABLE)
        if constraint.get("name")
    }


def upgrade() -> None:
    columns = _columns()
    if "palette_key" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "palette_key",
                sa.String(length=32),
                nullable=False,
                server_default="blue",
            ),
        )

    if PALETTE_CHECK not in _check_constraints():
        op.create_check_constraint(
            PALETTE_CHECK,
            TABLE,
            "palette_key IN ('blue', 'navy', 'gold', 'orange', 'emerald', 'forest', "
            "'violet', 'plum', 'rose', 'teal', 'cyan', 'slate')",
        )

    if "token_schema_version" in columns:
        op.execute(sa.text(f"UPDATE {TABLE} SET token_schema_version = 2"))
        op.alter_column(TABLE, "token_schema_version", server_default="2")

    # The tenant school name is authoritative. A second editable name creates
    # conflicting identity, while workspace backgrounds are not brandable.
    for name in ("brand_name", "background_color"):
        if name in columns:
            op.drop_column(TABLE, name)


def downgrade() -> None:
    columns = _columns()
    if "token_schema_version" in columns:
        op.execute(sa.text(f"UPDATE {TABLE} SET token_schema_version = 1"))
        op.alter_column(TABLE, "token_schema_version", server_default="1")
    if PALETTE_CHECK in _check_constraints():
        op.drop_constraint(PALETTE_CHECK, TABLE, type_="check")
    if "brand_name" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "brand_name",
                sa.String(length=255),
                nullable=False,
                server_default="Weave",
            ),
        )
    if "background_color" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "background_color",
                sa.String(length=7),
                nullable=False,
                server_default="#F8FAFC",
            ),
        )
    if "palette_key" in columns:
        op.drop_column(TABLE, "palette_key")
