"""Print semantic foreign-key differences between metadata and PostgreSQL."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import app.models  # noqa: E402,F401
from app.config.settings import settings  # noqa: E402
from app.shared.base_model import Base  # noqa: E402


def _schema(value: str | None) -> str:
    return value or "public"


def _action(value: str | None) -> str:
    normalized = (value or "").strip().upper().replace("_", " ")
    return "" if normalized in {"", "NO ACTION"} else normalized


def _signature(
    *,
    source_schema: str | None,
    source_table: str,
    local_columns: tuple[str, ...] | list[str],
    referent_schema: str | None,
    referent_table: str,
    remote_columns: tuple[str, ...] | list[str],
    ondelete: str | None = None,
    onupdate: str | None = None,
    deferrable: bool | None = None,
    initially: str | None = None,
) -> tuple[Any, ...]:
    return (
        _schema(source_schema),
        source_table,
        tuple(local_columns),
        _schema(referent_schema),
        referent_table,
        tuple(remote_columns),
        _action(ondelete),
        _action(onupdate),
        bool(deferrable),
        (initially or "").strip().upper(),
    )


def _metadata_signatures() -> set[tuple[Any, ...]]:
    signatures: set[tuple[Any, ...]] = set()
    for table in Base.metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            elements = tuple(constraint.elements)
            referred_table = elements[0].column.table
            signatures.add(
                _signature(
                    source_schema=table.schema,
                    source_table=table.name,
                    local_columns=tuple(column.name for column in constraint.columns),
                    referent_schema=referred_table.schema,
                    referent_table=referred_table.name,
                    remote_columns=tuple(element.column.name for element in elements),
                    ondelete=elements[0].ondelete if elements else None,
                    onupdate=elements[0].onupdate if elements else None,
                    deferrable=constraint.deferrable,
                    initially=constraint.initially,
                )
            )
    return signatures


def _database_signatures(sync_connection: Any) -> set[tuple[Any, ...]]:
    inspector = sa.inspect(sync_connection)
    signatures: set[tuple[Any, ...]] = set()
    for table_name in inspector.get_table_names(schema="public"):
        for foreign_key in inspector.get_foreign_keys(table_name, schema="public"):
            referred_table = foreign_key.get("referred_table")
            if not referred_table:
                continue
            options = foreign_key.get("options") or {}
            signatures.add(
                _signature(
                    source_schema="public",
                    source_table=table_name,
                    local_columns=foreign_key.get("constrained_columns") or (),
                    referent_schema=foreign_key.get("referred_schema"),
                    referent_table=referred_table,
                    remote_columns=foreign_key.get("referred_columns") or (),
                    ondelete=options.get("ondelete"),
                    onupdate=options.get("onupdate"),
                    deferrable=options.get("deferrable"),
                    initially=options.get("initially"),
                )
            )
    return signatures


async def main() -> None:
    database_url = settings.DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    engine = create_async_engine(database_url, connect_args={"statement_cache_size": 0})
    try:
        async with engine.connect() as connection:
            database = await connection.run_sync(_database_signatures)
    finally:
        await engine.dispose()

    metadata = _metadata_signatures()
    missing = sorted(metadata - database, key=repr)
    extra = sorted(database - metadata, key=repr)

    print(f"metadata_foreign_keys={len(metadata)}")
    print(f"database_foreign_keys={len(database)}")
    print(f"missing_from_database={len(missing)}")
    for signature in missing:
        print(f"MISSING {signature!r}")
    print(f"extra_in_database={len(extra)}")
    for signature in extra:
        print(f"EXTRA {signature!r}")


if __name__ == "__main__":
    asyncio.run(main())
