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


def _compare_type(
    migration_context: Any,
    inspected_column: Any,
    metadata_column: Any,
    inspected_type: Any,
    metadata_type: Any,
) -> bool | None:
    """Ignore schema-only differences for otherwise identical PostgreSQL enums."""

    _ = migration_context, inspected_column, metadata_column
    inspected_enums = tuple(getattr(inspected_type, "enums", ()) or ())
    metadata_enums = tuple(getattr(metadata_type, "enums", ()) or ())
    if inspected_enums and set(inspected_enums) == set(metadata_enums):
        inspected_name = getattr(inspected_type, "name", None)
        metadata_name = getattr(metadata_type, "name", None)
        if inspected_name == metadata_name:
            return False
    return None


def _normalized_schema(value: str | None) -> str:
    return value or "public"


def _normalized_fk_action(value: str | None) -> str:
    normalized = (value or "").strip().upper().replace("_", " ")
    return "" if normalized in {"", "NO ACTION"} else normalized


def _fk_signature(
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
        _normalized_schema(source_schema),
        source_table,
        tuple(local_columns),
        _normalized_schema(referent_schema),
        referent_table,
        tuple(remote_columns),
        _normalized_fk_action(ondelete),
        _normalized_fk_action(onupdate),
        bool(deferrable),
        (initially or "").strip().upper(),
    )


def _constraint_fk_signature(
    constraint: sa.ForeignKeyConstraint,
) -> tuple[Any, ...]:
    elements = tuple(constraint.elements)
    referred_table = elements[0].column.table
    return _fk_signature(
        source_schema=constraint.table.schema,
        source_table=constraint.table.name,
        local_columns=tuple(column.name for column in constraint.columns),
        referent_schema=referred_table.schema,
        referent_table=referred_table.name,
        remote_columns=tuple(element.column.name for element in elements),
        ondelete=elements[0].ondelete if elements else None,
        onupdate=elements[0].onupdate if elements else None,
        deferrable=constraint.deferrable,
        initially=constraint.initially,
    )


def _database_fk_signatures(connection: Any) -> set[tuple[Any, ...]]:
    inspector = sa.inspect(connection)
    available_tables = set(inspector.get_table_names(schema="public"))
    signatures: set[tuple[Any, ...]] = set()

    for table in target_metadata.tables.values():
        if table.name not in available_tables:
            continue
        schema = table.schema or "public"
        for reflected_fk in inspector.get_foreign_keys(table.name, schema=schema):
            referred_table = reflected_fk.get("referred_table")
            if not referred_table:
                continue
            options = reflected_fk.get("options") or {}
            signatures.add(
                _fk_signature(
                    source_schema=schema,
                    source_table=table.name,
                    local_columns=reflected_fk.get("constrained_columns") or (),
                    referent_schema=reflected_fk.get("referred_schema"),
                    referent_table=referred_table,
                    remote_columns=reflected_fk.get("referred_columns") or (),
                    ondelete=options.get("ondelete"),
                    onupdate=options.get("onupdate"),
                    deferrable=options.get("deferrable"),
                    initially=options.get("initially"),
                )
            )

    return signatures


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


def _include_object(existing_fk_signatures: set[tuple[Any, ...]]):
    def include_object(
        obj: Any,
        name: str | None,
        type_: str,
        reflected: bool,
        compare_to: Any,
    ) -> bool:
        """Suppress representation noise while preserving genuine schema drift."""

        if type_ == "table" and name == "alembic_version":
            return False

        if type_ == "index" and isinstance(obj, sa.Index) and compare_to is None:
            if obj.name != _schema_neutral_index_name(obj.name):
                return False
            if _index_signature(obj) in PUBLIC_SCHEMA_INDEX_SIGNATURES:
                return False

        if type_ == "unique_constraint" and isinstance(obj, sa.UniqueConstraint):
            columns = tuple(column.name for column in obj.columns)
            primary_key_columns = tuple(
                column.name for column in obj.table.primary_key.columns
            )
            if columns == ("id",) and primary_key_columns == ("id",):
                return False

        if (
            type_ == "foreign_key_constraint"
            and not reflected
            and compare_to is None
            and isinstance(obj, sa.ForeignKeyConstraint)
            and _constraint_fk_signature(obj) in existing_fk_signatures
        ):
            return False

        return True

    return include_object


def _configure_context(
    *,
    connection: Any | None = None,
    existing_fk_signatures: set[tuple[Any, ...]] | None = None,
) -> None:
    """Apply one comparison policy to online and offline migration runs."""

    options: dict[str, Any] = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "include_name": _include_name,
        "version_table_schema": "public",
        "compare_type": _compare_type,
        "compare_server_default": False,
        "include_object": _include_object(existing_fk_signatures or set()),
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
        _configure_context(
            connection=sync_connection,
            existing_fk_signatures=_database_fk_signatures(sync_connection),
        )
        with context.begin_transaction():
            context.run_migrations()

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
