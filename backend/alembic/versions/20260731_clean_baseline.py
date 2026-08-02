"""Clean baseline schema for Weave.

This revision intentionally replaces the previous development migration chain.
It is for fresh databases only: drop/recreate or migrate data manually before
using it against an existing database.

The baseline currently builds the first production schema from the registered
SQLAlchemy metadata. It must be replaced with explicit Alembic operations before
adding the next schema revision so future fresh databases cannot inherit model
changes twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401
from app.shared.base_model import Base


revision: str = "20260731_clean_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema(value: str | None) -> str:
    return value or "public"


def _foreign_key_signature(
    *,
    source_schema: str | None,
    source_table: str,
    local_columns: Sequence[str],
    referent_schema: str | None,
    referent_table: str,
    remote_columns: Sequence[str],
) -> tuple[Any, ...]:
    return (
        _schema(source_schema),
        source_table,
        tuple(local_columns),
        _schema(referent_schema),
        referent_table,
        tuple(remote_columns),
    )


def _database_foreign_keys(bind: Any) -> set[tuple[Any, ...]]:
    inspector = sa.inspect(bind)
    signatures: set[tuple[Any, ...]] = set()

    for table_name in inspector.get_table_names(schema="public"):
        for foreign_key in inspector.get_foreign_keys(table_name, schema="public"):
            referred_table = foreign_key.get("referred_table")
            if not referred_table:
                continue
            signatures.add(
                _foreign_key_signature(
                    source_schema="public",
                    source_table=table_name,
                    local_columns=foreign_key.get("constrained_columns") or (),
                    referent_schema=foreign_key.get("referred_schema"),
                    referent_table=referred_table,
                    remote_columns=foreign_key.get("referred_columns") or (),
                )
            )

    return signatures


def _metadata_foreign_key_signature(
    constraint: sa.ForeignKeyConstraint,
) -> tuple[Any, ...]:
    elements = tuple(constraint.elements)
    referred_table = elements[0].column.table
    return _foreign_key_signature(
        source_schema=constraint.table.schema,
        source_table=constraint.table.name,
        local_columns=tuple(column.name for column in constraint.columns),
        referent_schema=referred_table.schema,
        referent_table=referred_table.name,
        remote_columns=tuple(element.column.name for element in elements),
    )


def _metadata_foreign_key_count() -> int:
    return sum(
        len(table.foreign_key_constraints) for table in Base.metadata.tables.values()
    )


def _database_foreign_key_count(bind: Any) -> int:
    return int(
        bind.execute(
            sa.text(
                """
                SELECT count(*)
                FROM pg_constraint constraint_row
                JOIN pg_namespace namespace_row
                  ON namespace_row.oid = constraint_row.connamespace
                WHERE constraint_row.contype = 'f'
                  AND namespace_row.nspname = 'public'
                """
            )
        ).scalar_one()
    )


def _create_missing_foreign_keys(bind: Any) -> None:
    """Install every metadata FK and verify PostgreSQL persisted it."""

    existing = _database_foreign_keys(bind)
    for table in Base.metadata.sorted_tables:
        for constraint in table.foreign_key_constraints:
            signature = _metadata_foreign_key_signature(constraint)
            if signature in existing:
                continue

            ddl = str(
                sa.schema.AddConstraint(
                    constraint,
                    isolate_from_table=False,
                ).compile(
                    dialect=bind.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )
            bind.exec_driver_sql(ddl)
            existing.add(signature)

    expected = _metadata_foreign_key_count()
    actual = _database_foreign_key_count(bind)
    if actual != expected:
        raise RuntimeError(
            "Incomplete baseline foreign-key installation: "
            f"expected {expected}, PostgreSQL contains {actual}."
        )


def upgrade() -> None:
    """Create the complete initial schema on a fresh database."""

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    _create_missing_foreign_keys(bind)


def downgrade() -> None:
    """Refuse an operation that would erase the complete application schema."""

    raise RuntimeError(
        "Downgrading below the Weave baseline is not supported. "
        "Restore a backup or recreate the database explicitly."
    )
