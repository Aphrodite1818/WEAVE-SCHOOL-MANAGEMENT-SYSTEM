"""Safety and idempotency checks for first-install schema bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.config import database_bootstrap
from app.config.database_bootstrap import BootstrapResult, SchemaState, classify_schema_state
from app.shared.base_model import Base


class _ScalarResult:
    def __init__(self, values: set[str]) -> None:
        self._values = values

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._values)


class _Connection:
    def __init__(self, tables: set[str]) -> None:
        self.tables = tables
        self.execute = AsyncMock(side_effect=self._execute)
        self.run_sync = AsyncMock()

    async def _execute(self, statement, parameters=None):
        del parameters
        if "pg_catalog.pg_tables" in str(statement):
            return _ScalarResult(self.tables)
        return _ScalarResult(set())


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def begin(self):
        yield self.connection


def _expected_tables() -> set[str]:
    return {table.name for table in Base.metadata.tables.values()}


def test_fresh_database_detection_requires_no_tables_or_marker() -> None:
    expected = _expected_tables()
    assert classify_schema_state(set(), expected) is SchemaState.FRESH
    assert classify_schema_state({"alembic_version"}, expected) is SchemaState.PARTIAL


@pytest.mark.asyncio
async def test_fresh_database_is_created_and_stamped_once(monkeypatch) -> None:
    connection = _Connection(set())
    initialize = AsyncMock()
    monkeypatch.setattr(database_bootstrap, "_initialize_fresh_schema", initialize)

    result = await database_bootstrap.bootstrap_database(_Engine(connection))

    assert result == BootstrapResult(state=SchemaState.FRESH, initialized_now=True)
    initialize.assert_awaited_once_with(connection)


@pytest.mark.asyncio
async def test_initialized_database_does_not_recreate_or_stamp(monkeypatch) -> None:
    connection = _Connection(_expected_tables() | {"alembic_version"})
    initialize = AsyncMock()
    monkeypatch.setattr(database_bootstrap, "_initialize_fresh_schema", initialize)

    first = await database_bootstrap.bootstrap_database(_Engine(connection))
    second = await database_bootstrap.bootstrap_database(_Engine(connection))

    assert (
        first
        == second
        == BootstrapResult(
            state=SchemaState.INITIALIZED,
            initialized_now=False,
        )
    )
    initialize.assert_not_awaited()
    connection.run_sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_schema_refuses_automatic_repair_in_every_environment(monkeypatch) -> None:
    connection = _Connection({next(iter(_expected_tables()))})
    initialize = AsyncMock()
    monkeypatch.setattr(database_bootstrap, "_initialize_fresh_schema", initialize)

    with pytest.raises(RuntimeError, match="Refusing automatic repair or stamping"):
        await database_bootstrap.bootstrap_database(_Engine(connection))

    initialize.assert_not_awaited()
    connection.run_sync.assert_not_awaited()
