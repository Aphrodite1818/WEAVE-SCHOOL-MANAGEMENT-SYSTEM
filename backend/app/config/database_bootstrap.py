"""First-install PostgreSQL schema bootstrap.

This module creates the current model schema only when the public schema is
genuinely empty. Existing and partially initialized databases are never
repaired, stamped, dropped, or recreated during application startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.config.logging import get_logger
from app.shared.base_model import Base

BASELINE_REVISION = "20260911_initial_schema"
_BOOTSTRAP_LOCK_KEY = 8_733_241_109_202_609_11
_ALEMBIC_VERSION_TABLE = "alembic_version"

logger = get_logger(__name__)


class SchemaState(str, Enum):
    FRESH = "fresh"
    INITIALIZED = "initialized"
    PARTIAL = "partial"


@dataclass(frozen=True)
class BootstrapResult:
    state: SchemaState
    initialized_now: bool


def classify_schema_state(
    existing_tables: set[str],
    expected_tables: set[str],
) -> SchemaState:
    """Classify without guessing that a partial schema is safe to repair."""

    application_tables = existing_tables - {_ALEMBIC_VERSION_TABLE}
    if not application_tables and _ALEMBIC_VERSION_TABLE not in existing_tables:
        return SchemaState.FRESH
    if expected_tables and expected_tables.issubset(application_tables):
        return SchemaState.INITIALIZED
    return SchemaState.PARTIAL


async def _read_public_table_names(connection: AsyncConnection) -> set[str]:
    result = await connection.execute(
        text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
    )
    return set(result.scalars())


async def _initialize_fresh_schema(connection: AsyncConnection) -> None:
    await connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    await connection.run_sync(
        lambda sync_connection: Base.metadata.create_all(
            bind=sync_connection,
            checkfirst=False,
        )
    )
    await connection.execute(
        text(
            "CREATE TABLE public.alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
            ")"
        )
    )
    await connection.execute(
        text("INSERT INTO public.alembic_version (version_num) VALUES (:revision)"),
        {"revision": BASELINE_REVISION},
    )


async def bootstrap_database(engine: AsyncEngine) -> BootstrapResult:
    """Create and stamp the schema once, serialized by a PostgreSQL lock."""

    configure_mappers()
    expected_tables = {table.name for table in Base.metadata.tables.values()}
    if not expected_tables:
        raise RuntimeError("The SQLAlchemy model registry is empty; refusing database bootstrap.")

    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _BOOTSTRAP_LOCK_KEY},
        )
        existing_tables = await _read_public_table_names(connection)
        state = classify_schema_state(existing_tables, expected_tables)

        if state is SchemaState.INITIALIZED:
            logger.info("Database schema already initialized; bootstrap skipped")
            return BootstrapResult(state=state, initialized_now=False)
        if state is SchemaState.PARTIAL:
            present = len((existing_tables - {_ALEMBIC_VERSION_TABLE}) & expected_tables)
            raise RuntimeError(
                "Database schema is partially initialized or has a migration marker without "
                f"the complete Weave schema ({present}/{len(expected_tables)} model tables present). "
                "Refusing automatic repair or stamping."
            )

        await _initialize_fresh_schema(connection)
        logger.info(
            "Fresh database schema initialized",
            extra={"baseline_revision": BASELINE_REVISION, "table_count": len(expected_tables)},
        )
        return BootstrapResult(state=state, initialized_now=True)
