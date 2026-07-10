from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Iterable

from redis.asyncio import Redis

from app.config.logging import get_logger
from app.config.settings import settings


logger = get_logger(__name__)

_CONSUME_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""

_rate_limit_redis_client: Redis | None = None
_fallback_records: defaultdict[str, list[float]] = defaultdict(list)
_fallback_lock = Lock()
_last_redis_error_log_at = 0.0
_REDIS_ERROR_LOG_INTERVAL_SECONDS = 60


@dataclass(frozen=True)
class RateLimitResult:
    """Current state of one rate-limit bucket."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int
    current: int


def _log_redis_fallback(error: Exception) -> None:
    """Log Redis limiter fallback without flooding logs."""

    global _last_redis_error_log_at

    now = time.time()
    if now - _last_redis_error_log_at < _REDIS_ERROR_LOG_INTERVAL_SECONDS:
        return

    _last_redis_error_log_at = now
    logger.warning(
        "Redis rate limiter unavailable; using in-memory fallback.",
        extra={"error": str(error)},
    )


def _prune_fallback_records(
    key: str,
    *,
    now: float,
    window_seconds: int,
) -> list[float]:
    """Return unexpired local fallback hits for a key."""

    records = [
        timestamp
        for timestamp in _fallback_records[key]
        if now - timestamp < window_seconds
    ]
    _fallback_records[key] = records
    return records


def _fallback_status(
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    """Return local fallback state without consuming a hit."""

    now = time.time()

    with _fallback_lock:
        records = _prune_fallback_records(
            key,
            now=now,
            window_seconds=window_seconds,
        )
        current = len(records)
        allowed = current < limit

        retry_after = 0
        reset_after = 0
        if records:
            reset_after = max(int(window_seconds - (now - records[0])), 1)
            retry_after = reset_after if not allowed else 0

    return RateLimitResult(
        allowed=allowed,
        limit=limit,
        remaining=max(limit - current, 0),
        retry_after=retry_after,
        reset_after=reset_after,
        current=current,
    )


def _fallback_consume(
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    """Consume one hit in the local fallback limiter."""

    now = time.time()

    with _fallback_lock:
        records = _prune_fallback_records(
            key,
            now=now,
            window_seconds=window_seconds,
        )
        records.append(now)
        _fallback_records[key] = records

        current = len(records)
        allowed = current <= limit

        reset_after = max(int(window_seconds - (now - records[0])), 1)
        retry_after = reset_after if not allowed else 0

    return RateLimitResult(
        allowed=allowed,
        limit=limit,
        remaining=max(limit - current, 0),
        retry_after=retry_after,
        reset_after=reset_after,
        current=current,
    )


def _fallback_clear(keys: Iterable[str]) -> None:
    """Clear local fallback counters."""

    key_list = [key for key in keys if key]
    if not key_list:
        return

    with _fallback_lock:
        for key in key_list:
            _fallback_records.pop(key, None)


async def get_rate_limit_redis_client() -> Redis:
    """Return a Redis client dedicated to rate limiting."""

    global _rate_limit_redis_client

    if _rate_limit_redis_client is not None:
        return _rate_limit_redis_client

    redis_url = settings.RATE_LIMIT_REDIS_URL or settings.REDIS_URL
    if not redis_url:
        raise RuntimeError("Redis URL is required for rate limiting.")

    _rate_limit_redis_client = Redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )

    await _rate_limit_redis_client.ping()
    return _rate_limit_redis_client


class RedisFixedWindowRateLimiter:
    """Fixed-window Redis limiter with in-memory fallback during Redis outages."""

    async def status(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Return current bucket state without consuming a hit."""

        try:
            client = await get_rate_limit_redis_client()

            raw_current = await client.get(key)
            current = int(raw_current or 0)

            ttl = await client.ttl(key) if current > 0 else 0
            if ttl < 0:
                ttl = window_seconds if current > 0 else 0

            allowed = current < limit

            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=max(limit - current, 0),
                retry_after=ttl if not allowed else 0,
                reset_after=ttl,
                current=current,
            )
        except Exception as exc:
            _log_redis_fallback(exc)
            return _fallback_status(
                key,
                limit=limit,
                window_seconds=window_seconds,
            )

    async def consume(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Consume one hit from a rate-limit bucket."""

        try:
            client = await get_rate_limit_redis_client()
            current, ttl = await client.eval(
                _CONSUME_SCRIPT,
                1,
                key,
                window_seconds,
            )

            current = int(current)
            ttl = int(ttl)
            if ttl < 0:
                ttl = window_seconds

            allowed = current <= limit

            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=max(limit - current, 0),
                retry_after=ttl if not allowed else 0,
                reset_after=ttl,
                current=current,
            )
        except Exception as exc:
            _log_redis_fallback(exc)
            return _fallback_consume(
                key,
                limit=limit,
                window_seconds=window_seconds,
            )

    async def clear(self, keys: Iterable[str]) -> None:
        """Delete rate-limit counters."""

        key_list = [key for key in keys if key]
        if not key_list:
            return

        _fallback_clear(key_list)

        try:
            client = await get_rate_limit_redis_client()
            await client.delete(*key_list)
        except Exception as exc:
            _log_redis_fallback(exc)
