"""staging branch baseline schema

Revision ID: 20260630_staging_branch_baseline
Revises:
Create Date: 2026-06-30 02:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.modules import import_model_modules
from app.shared.base_model import Base


revision: str = "20260630_staging_branch_baseline"
down_revision: Union[str, Sequence[str], None] = "1db81d711bbc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_metadata_server_defaults() -> None:
    """Normalize SQL expression defaults before create_all emits DDL.

    This baseline migration builds the schema from model metadata. Some model
    defaults are stored as plain strings, which PostgreSQL receives as quoted
    literals, e.g. DEFAULT 'CURRENT_DATE'. Convert known SQL defaults to real
    SQL expressions before emitting the baseline schema.
    """

    sql_defaults = {
        "CURRENT_DATE": sa.text("CURRENT_DATE"),
        "now()": sa.text("now()"),
        "true": sa.text("true"),
        "false": sa.text("false"),
        "1": sa.text("1"),
        "0": sa.text("0"),
    }

    for table in Base.metadata.tables.values():
        for column in table.columns:
            server_default = column.server_default
            if server_default is None:
                continue

            default_arg = getattr(server_default, "arg", None)
            if not isinstance(default_arg, str):
                continue

            normalized_default = sql_defaults.get(default_arg)
            if normalized_default is None:
                continue

            column.server_default = sa.schema.DefaultClause(normalized_default)


def upgrade() -> None:
    """Create the full staging schema from the current model metadata."""

    import_model_modules()
    _normalize_metadata_server_defaults()
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Staging baseline is not intended to be downgraded."""

    pass
