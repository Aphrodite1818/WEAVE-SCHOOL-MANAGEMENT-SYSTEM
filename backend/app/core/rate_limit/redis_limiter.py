#==========================#
#   rate limiter .py       #
#==========================#





from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from redis.asyncio import Redis

from app.config.settings import settings


_CONSUME_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""


_rate_limit_redis_client: Redis | None = None


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int
    current: int


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
    """Fixed-window Redis limiter using atomic INCR + EXPIRE."""

    async def status(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Return current rate-limit state without consuming a hit."""

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

    async def consume(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Consume one hit from a rate-limit bucket."""

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

    async def clear(self, keys: Iterable[str]) -> None:
        """Delete rate-limit counters."""

        key_list = [key for key in keys if key]
        if not key_list:
            return

        client = await get_rate_limit_redis_client()
        await client.delete(*key_list)