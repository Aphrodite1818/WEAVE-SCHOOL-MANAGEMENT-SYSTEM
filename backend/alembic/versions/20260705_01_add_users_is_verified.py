"""add users.is_verified column

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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # If users table doesn't exist, nothing to do here.
    if "users" not in inspector.get_table_names(schema=PUBLIC_SCHEMA):
        return

    cols = [c["name"] for c in inspector.get_columns("users", schema=PUBLIC_SCHEMA)]
    if "is_verified" in cols:
        return

    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names(schema=PUBLIC_SCHEMA):
        return

    cols = [c["name"] for c in inspector.get_columns("users", schema=PUBLIC_SCHEMA)]
    if "is_verified" not in cols:
        return

    op.drop_column("users", "is_verified", schema=PUBLIC_SCHEMA)
