from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config.settings import settings  # noqa: E402
import app.models  # noqa: E402,F401
from app.shared.base_model import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def _normalized_compiled_type(dialect: Any, column_type: Any) -> str:
    """Compile a type through the active dialect for semantic comparison."""

    implementation = column_type.dialect_impl(dialect)
    compiled = dialect.type_compiler.process(implementation)
    return " ".join(compiled.upper().split())


def _compare_type(
    migration_context: Any,
    inspected_column: Any,
    metadata_column: Any,
    inspected_type: Any,
    metadata_type: Any,
) -> bool | None:
    """Suppress PostgreSQL reflection noise while preserving real type drift."""

    _ = inspected_column, metadata_column

    inspected_enums = tuple(getattr(inspected_type, "enums", ()) or ())
    metadata_enums = tuple(getattr(metadata_type, "enums", ()) or ())
    if inspected_enums and set(inspected_enums) == set(metadata_enums):
        inspected_name = getattr(inspected_type, "name", None)
        metadata_name = getattr(metadata_type, "name", None)
        if inspected_name == metadata_name:
            return False

    # SQLAlchemy may reflect a non-native Enum, including an Enum used as an
    # ARRAY item type, as its VARCHAR implementation. If both sides compile to
    # the same PostgreSQL type, they are semantically identical even though
    # Alembic's generic token comparison reports Enum versus VARCHAR.
    try:
        inspected_compiled = _normalized_compiled_type(
            migration_context.dialect,
            inspected_type,
        )
        metadata_compiled = _normalized_compiled_type(
            migration_context.dialect,
            metadata_type,
        )
    except (AttributeError, TypeError, ValueError):
        return None

    if inspected_compiled == metadata_compiled:
        return False

    return None


def _schema_neutral_index_name(name: str | None) -> str:
    return (name or "").replace("ix_public_", "ix_", 1)


def _index_signature(index: sa.Index) -> tuple[Any, ...]:
    return (
        index.table.name,
        tuple(column.name for column in index.columns),
        bool(index.unique),
        _schema_neutral_index_name(index.name),
    )


def _public_schema_index_signatures() -> set[tuple[Any, ...]]:
    signatures: set[tuple[Any, ...]] = set()
    for table in target_metadata.tables.values():
        for index in table.indexes:
            if index.name != _schema_neutral_index_name(index.name):
                signatures.add(_index_signature(index))
    return signatures


PUBLIC_SCHEMA_INDEX_SIGNATURES = _public_schema_index_signatures()


def _include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    """Limit autogeneration to the application's public PostgreSQL schema."""

    _ = parent_names
    if type_ == "schema":
        return name in {None, "public"}
    return True


def _include_object(
    obj: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Suppress known representation noise without hiding real schema drift."""

    _ = reflected

    if type_ == "table" and name == "alembic_version":
        return False

    if type_ == "index" and isinstance(obj, sa.Index) and compare_to is None:
        if obj.name != _schema_neutral_index_name(obj.name):
            return False
        if _index_signature(obj) in PUBLIC_SCHEMA_INDEX_SIGNATURES:
            return False

    if type_ == "unique_constraint" and isinstance(obj, sa.UniqueConstraint):
        columns = tuple(column.name for column in obj.columns)
        primary_key_columns = tuple(column.name for column in obj.table.primary_key.columns)
        if columns == ("id",) and primary_key_columns == ("id",):
            return False

    return True


def _configure_context(*, connection: Any | None = None) -> None:
    """Apply one comparison policy to online and offline migration runs."""

    options: dict[str, Any] = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "include_name": _include_name,
        "version_table_schema": "public",
        "compare_type": _compare_type,
        "compare_server_default": False,
        "include_object": _include_object,
    }
    if connection is None:
        options.update(
            {
                "url": settings.DATABASE_URL or "",
                "literal_binds": True,
                "dialect_opts": {"paramstyle": "named"},
            }
        )
    else:
        options["connection"] = connection

    context.configure(**options)


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    _configure_context()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    database_url = (settings.DATABASE_URL or "").replace("%", "%%")
    config.set_main_option("sqlalchemy.url", database_url)

    def do_run_migrations(sync_connection: Any) -> None:
        _configure_context(connection=sync_connection)

        try:
            with context.begin_transaction():
                context.run_migrations()

            # Persist both transactional DDL and the alembic_version update when
            # Alembic joins SQLAlchemy's implicit transaction on an async bridge.
            if sync_connection.in_transaction():
                sync_connection.commit()
        except Exception:
            if sync_connection.in_transaction():
                sync_connection.rollback()
            raise

    async def run_async_migrations() -> None:
        connectable = async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            connect_args={"statement_cache_size": 0},
        )

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
