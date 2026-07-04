"""add actor is_verified columns safely

Revision ID: 20260705_add_users_is_verified
Revises: 20260704_subscription_billing
Create Date: 2026-07-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260705_add_users_is_verified"
down_revision = "20260704_subscription_billing"
branch_labels = None
depends_on = None

PUBLIC_SCHEMA = "public"


ACTOR_TABLES = {
    "tenant_admins": {
        "active_predicate": "account_status = 'active' OR is_active = true",
    },
    "teachers": {
        "active_predicate": "account_status = 'active' OR is_active = true",
    },
    "parents": {
        "active_predicate": "account_status = 'active' OR is_active = true",
    },
    "students": {
        "active_predicate": "account_status = 'active' OR is_active = true",
    },
}


OPTIONAL_LEGACY_TABLES = {
    "users": {
        "active_predicate": "is_active = true",
    },
}


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names(schema=PUBLIC_SCHEMA)


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in [
        column["name"]
        for column in inspector.get_columns(table_name, schema=PUBLIC_SCHEMA)
    ]


def _add_is_verified_column(
    *,
    inspector: sa.Inspector,
    table_name: str,
    active_predicate: str,
) -> None:
    if not _table_exists(inspector, table_name):
        return

    if _column_exists(inspector, table_name, "is_verified"):
        return

    op.add_column(
        table_name,
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=PUBLIC_SCHEMA,
    )

    # Existing active accounts predate the explicit verification column in some
    # environments. Mark them verified so the new auth guards do not lock out
    # already usable accounts after the migration runs. New pending accounts keep
    # the model/server default of false.
    op.execute(
        sa.text(
            f"""
            UPDATE {PUBLIC_SCHEMA}.{table_name}
            SET is_verified = true
            WHERE {active_predicate}
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, config in {**ACTOR_TABLES, **OPTIONAL_LEGACY_TABLES}.items():
        _add_is_verified_column(
            inspector=inspector,
            table_name=table_name,
            active_predicate=config["active_predicate"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in [*OPTIONAL_LEGACY_TABLES.keys(), *ACTOR_TABLES.keys()]:
        if not _table_exists(inspector, table_name):
            continue

        if not _column_exists(inspector, table_name, "is_verified"):
            continue

        op.drop_column(table_name, "is_verified", schema=PUBLIC_SCHEMA)
