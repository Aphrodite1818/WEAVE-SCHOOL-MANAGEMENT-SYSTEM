from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.dialects import postgresql
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
    if isinstance(inspected_type, postgresql.ENUM) and isinstance(metadata_type, postgresql.ENUM):
        if inspected_type.name == metadata_type.name and tuple(inspected_type.enums or ()) == tuple(
            metadata_type.enums or ()
        ):
            return False
    return None


def _foreign_key_signature(constraint: sa.ForeignKeyConstraint) -> tuple[Any, ...]:
    """Return a schema-neutral signature for one foreign-key constraint."""

    local_columns = tuple(column.name for column in constraint.columns)
    remote_columns = tuple(
        element.target_fullname.removeprefix("public.") for element in constraint.elements
    )
    ondelete = tuple((element.ondelete or "").upper() for element in constraint.elements)
    onupdate = tuple((element.onupdate or "").upper() for element in constraint.elements)
    return (
        local_columns,
        remote_columns,
        ondelete,
        onupdate,
        bool(constraint.deferrable),
        constraint.initially,
    )


def _include_object(
    obj: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Suppress comparison noise while preserving genuine schema drift."""

    _ = name, reflected

    if type_ == "unique_constraint" and isinstance(obj, sa.UniqueConstraint):
        columns = tuple(column.name for column in obj.columns)
        primary_key_columns = tuple(column.name for column in obj.table.primary_key.columns)
        if columns == ("id",) and primary_key_columns == ("id",):
            return False

    if (
        type_ == "foreign_key_constraint"
        and isinstance(obj, sa.ForeignKeyConstraint)
        and isinstance(compare_to, sa.ForeignKeyConstraint)
        and _foreign_key_signature(obj) == _foreign_key_signature(compare_to)
    ):
        return False

    return True


def _configure_context(*, connection: Any | None = None) -> None:
    """Apply one comparison policy to online and offline migration runs."""

    options: dict[str, Any] = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "version_table_schema": "public",
        "compare_type": _compare_type,
        "compare_server_default": True,
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
