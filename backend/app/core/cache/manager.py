# ========================== #
#    core/cache/manager.py   #
# ========================== #

"""Fail-safe Redis cache operations shared by application services."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.config.logging import get_logger
from app.core.cache.redis import get_redis
from app.core.cache.serialization import dumps, loads

logger = get_logger(__name__)

T = TypeVar("T")

_CACHE_DELETE_BATCH_SIZE = 500


class CacheManager:
    """Small fail-safe wrapper around Redis operations.

    Redis failures must not make the primary application workflow fail. The
    database remains the source of truth, while Redis is treated as an optional
    acceleration layer.
    """

    _inflight: dict[str, asyncio.Task[Any]] = {}
    _inflight_guard = asyncio.Lock()

    @staticmethod
    async def get_json(key: str) -> Any | None:
        """Return a decoded JSON value, or ``None`` on miss/unavailability."""

        redis = get_redis()
        if redis is None:
            return None

        try:
            cached_value = await redis.get(key)
            if cached_value is None:
                return None
            return loads(cached_value)
        except Exception:
            logger.exception("Failed to read JSON cache value", extra={"cache_key": key})
            return None

    @staticmethod
    async def set_json(key: str, value: Any, ttl: int) -> bool:
        """Store a JSON value with a positive TTL measured in seconds."""

        if ttl <= 0:
            raise ValueError("Cache TTL must be greater than zero")

        redis = get_redis()
        if redis is None:
            return False

        try:
            await redis.set(key, dumps(value), ex=ttl)
            return True
        except Exception:
            logger.exception("Failed to write JSON cache value", extra={"cache_key": key})
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        """Delete one key without blocking Redis on value memory reclamation."""

        redis = get_redis()
        if redis is None:
            return False

        try:
            await redis.unlink(key)
            return True
        except Exception:
            logger.exception("Failed to delete cache key", extra={"cache_key": key})
            return False

    @staticmethod
    async def delete_many(keys: list[str]) -> int:
        """Delete cache keys in bounded, non-blocking batches."""

        if not keys:
            return 0

        redis = get_redis()
        if redis is None:
            return 0

        unique_keys = list(dict.fromkeys(keys))
        deleted_count = 0

        try:
            for start in range(0, len(unique_keys), _CACHE_DELETE_BATCH_SIZE):
                batch = unique_keys[start : start + _CACHE_DELETE_BATCH_SIZE]
                deleted_count += int(await redis.unlink(*batch))
            return deleted_count
        except Exception:
            logger.exception(
                "Failed to delete cache-key batch",
                extra={"cache_key_count": len(unique_keys)},
            )
            return deleted_count

    @staticmethod
    async def delete_pattern(pattern: str, batch_size: int = 500) -> int:
        """Delete keys matching a pattern using SCAN and bounded UNLINK calls."""

        if batch_size <= 0:
            raise ValueError("Cache scan batch size must be greater than zero")

        redis = get_redis()
        if redis is None:
            return 0

        deleted_count = 0

        try:
            cursor: int | str = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=batch_size,
                )
                if keys:
                    for start in range(0, len(keys), _CACHE_DELETE_BATCH_SIZE):
                        batch = keys[start : start + _CACHE_DELETE_BATCH_SIZE]
                        deleted_count += int(await redis.unlink(*batch))

                if int(cursor) == 0:
                    break

            return deleted_count
        except Exception:
            logger.exception(
                "Failed to delete cache keys by pattern",
                extra={"cache_pattern": pattern},
            )
            return deleted_count

    @staticmethod
    async def exists(key: str) -> bool:
        """Return whether a cache key currently exists."""

        redis = get_redis()
        if redis is None:
            return False

        try:
            return bool(await redis.exists(key))
        except Exception:
            logger.exception("Failed to check cache-key existence", extra={"cache_key": key})
            return False

    @classmethod
    async def _remove_inflight(
        cls,
        key: str,
        task: asyncio.Task[Any],
    ) -> None:
        async with cls._inflight_guard:
            if cls._inflight.get(key) is task:
                cls._inflight.pop(key, None)

    @classmethod
    def _schedule_inflight_cleanup(
        cls,
        key: str,
        task: asyncio.Task[Any],
    ) -> None:
        try:
            asyncio.get_running_loop().create_task(cls._remove_inflight(key, task))
        except RuntimeError:
            cls._inflight.pop(key, None)

    @classmethod
    async def get_or_set(
        cls,
        key: str,
        fetcher: Callable[[], Awaitable[T]],
        ttl: int,
    ) -> T:
        """Return cached data or coalesce concurrent misses into one fetch.

        Without single-flight protection, several simultaneous dashboard
        requests can all observe the same cache miss and execute the same heavy
        database query chain. Requests for the same key now await one shared
        population task within the current application process.
        """

        cached_value = await cls.get_json(key)
        if cached_value is not None:
            return cached_value

        async def populate() -> T:
            # Another process may have populated Redis between the initial miss
            # and this task starting, so check once more before querying the DB.
            second_check = await cls.get_json(key)
            if second_check is not None:
                return second_check

            fresh_value = await fetcher()
            await cls.set_json(key, fresh_value, ttl)
            return fresh_value

        async with cls._inflight_guard:
            task = cls._inflight.get(key)
            if task is None:
                task = asyncio.create_task(populate())
                cls._inflight[key] = task
                task.add_done_callback(
                    lambda completed_task, cache_key=key: cls._schedule_inflight_cleanup(
                        cache_key,
                        completed_task,
                    )
                )

        # Shield the shared task so cancellation of one request does not cancel
        # cache population for every other request awaiting the same key.
        return await asyncio.shield(task)
