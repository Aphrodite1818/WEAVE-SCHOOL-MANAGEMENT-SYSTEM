"""Application startup orders schema bootstrap before database consumers."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

import app.main as main_module


@pytest.mark.asyncio
async def test_existing_schema_startup_continues_without_recreation(monkeypatch) -> None:
    events: list[str] = []

    async def record(name: str) -> None:
        events.append(name)

    @asynccontextmanager
    async def session_factory():
        class Session:
            @asynccontextmanager
            async def begin(self):
                yield

        yield Session()

    monkeypatch.setattr(main_module, "bootstrap_database", lambda engine: record("bootstrap"))
    monkeypatch.setattr(main_module, "connect_redis", lambda: record("redis"))
    monkeypatch.setattr(main_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        main_module.SuperadminBootstrapService,
        "ensure_bootstrap_superadmin",
        lambda db: record("superadmin"),
    )
    monkeypatch.setattr(main_module.realtime_broker, "start", lambda: record("realtime-start"))
    monkeypatch.setattr(main_module.cbt_sync_listener, "start", lambda: record("cbt-start"))
    monkeypatch.setattr(main_module.cbt_sync_listener, "stop", lambda: record("cbt-stop"))
    monkeypatch.setattr(main_module.realtime_broker, "stop", lambda: record("realtime-stop"))
    monkeypatch.setattr(main_module, "close_redis", lambda: record("redis-close"))
    monkeypatch.setattr(
        main_module,
        "engine",
        type("Engine", (), {"dispose": lambda self: record("engine-close")})(),
    )
    monkeypatch.setattr(main_module, "flush_sentry", lambda: record("sentry-flush"))

    async with main_module.lifespan(main_module.app):
        events.append("serving")

    assert events[:5] == ["bootstrap", "redis", "superadmin", "realtime-start", "cbt-start"]
    assert "serving" in events
