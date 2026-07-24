from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache.events import (
    discard_cache_invalidation_events,
    flush_cache_invalidation_events,
    queue_cache_key_invalidation,
    queue_cache_pattern_invalidation,
)


def _db() -> SimpleNamespace:
    return SimpleNamespace(sync_session=SimpleNamespace(info={}))


@pytest.mark.asyncio
async def test_flush_runs_queued_cache_invalidations_once() -> None:
    db = _db()

    queue_cache_key_invalidation(db, "tenant:one:dashboard", "tenant:one:dashboard")
    queue_cache_pattern_invalidation(db, "tenant:one:subscriptions:*")

    with (
        patch(
            "app.core.cache.events.CacheManager.delete_many",
            new=AsyncMock(return_value=1),
        ) as delete_many,
        patch(
            "app.core.cache.events.CacheManager.delete_pattern",
            new=AsyncMock(return_value=3),
        ) as delete_pattern,
    ):
        deleted_count = await flush_cache_invalidation_events(db)
        second_deleted_count = await flush_cache_invalidation_events(db)

    assert deleted_count == 4
    assert second_deleted_count == 0
    delete_many.assert_awaited_once_with(["tenant:one:dashboard"])
    delete_pattern.assert_awaited_once_with("tenant:one:subscriptions:*")


@pytest.mark.asyncio
async def test_discard_prevents_rollback_invalidations() -> None:
    db = _db()
    queue_cache_key_invalidation(db, "tenant:one:branding")
    discard_cache_invalidation_events(db)

    with patch(
        "app.core.cache.events.CacheManager.delete_many",
        new=AsyncMock(),
    ) as delete_many:
        deleted_count = await flush_cache_invalidation_events(db)

    assert deleted_count == 0
    delete_many.assert_not_awaited()
