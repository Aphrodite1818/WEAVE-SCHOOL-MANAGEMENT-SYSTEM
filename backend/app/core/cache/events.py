"""Transaction-aware cache invalidation events.

Services should register cache invalidations while making database changes.
The request/session boundary flushes those events only after a successful
commit, so Redis never gets invalidated for data that later rolls back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.core.cache.manager import CacheManager

logger = get_logger(__name__)

CACHE_INVALIDATION_EVENTS = "cache_invalidation_events"

CacheInvalidationKind = Literal["key", "pattern"]


@dataclass(frozen=True, slots=True)
class CacheInvalidationEvent:
    """One cache invalidation requested by a committed domain event."""

    kind: CacheInvalidationKind
    value: str


def _session_info(db: AsyncSession) -> dict | None:
    info = getattr(getattr(db, "sync_session", None), "info", None)
    return info if isinstance(info, dict) else None


def _event_bucket(db: AsyncSession) -> set[CacheInvalidationEvent]:
    info = _session_info(db)
    if info is None:
        return set()
    return info.setdefault(CACHE_INVALIDATION_EVENTS, set())


def queue_cache_key_invalidation(db: AsyncSession, *keys: str) -> None:
    """Queue key deletions to run after the surrounding transaction commits."""

    bucket = _event_bucket(db)
    for key in keys:
        if key:
            bucket.add(CacheInvalidationEvent(kind="key", value=key))


def queue_cache_pattern_invalidation(db: AsyncSession, *patterns: str) -> None:
    """Queue pattern deletions to run after the surrounding transaction commits."""

    bucket = _event_bucket(db)
    for pattern in patterns:
        if pattern:
            bucket.add(CacheInvalidationEvent(kind="pattern", value=pattern))


def discard_cache_invalidation_events(db: AsyncSession) -> None:
    """Drop queued cache events after rollback or abandoned work."""

    info = _session_info(db)
    if info is not None:
        info.pop(CACHE_INVALIDATION_EVENTS, None)


async def flush_cache_invalidation_events(db: AsyncSession) -> int:
    """Run queued invalidations after a successful commit.

    Cache failures are logged and swallowed because the database is still the
    source of truth. The return value is the number of Redis keys Redis reported
    as deleted.
    """

    info = _session_info(db)
    if info is None:
        return 0

    events = tuple(info.pop(CACHE_INVALIDATION_EVENTS, set()))
    if not events:
        return 0

    deleted_count = 0
    key_events = [event.value for event in events if event.kind == "key"]
    pattern_events = [event.value for event in events if event.kind == "pattern"]

    if key_events:
        deleted_count += await CacheManager.delete_many(key_events)

    for pattern in pattern_events:
        deleted_count += await CacheManager.delete_pattern(pattern)

    return deleted_count


async def invalidate_cache_key_now(*keys: str) -> int:
    """Immediately delete cache keys for non-transactional maintenance paths."""

    try:
        return await CacheManager.delete_many([key for key in keys if key])
    except Exception:
        logger.exception("Immediate cache-key invalidation failed")
        return 0


async def invalidate_cache_pattern_now(*patterns: str) -> int:
    """Immediately delete cache patterns for non-transactional maintenance paths."""

    deleted_count = 0
    for pattern in patterns:
        if not pattern:
            continue
        try:
            deleted_count += await CacheManager.delete_pattern(pattern)
        except Exception:
            logger.exception(
                "Immediate cache-pattern invalidation failed",
                extra={"cache_pattern": pattern},
            )
    return deleted_count
