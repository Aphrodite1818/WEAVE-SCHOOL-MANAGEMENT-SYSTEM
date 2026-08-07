from __future__ import annotations

import pytest

from app.config.settings import EnvironmentType, settings
from app.core.rate_limits import redis_limiter
from app.core.rate_limits.redis_limiter import RedisFixedWindowRateLimiter


async def _unavailable_client():
    raise RuntimeError("redis unavailable")


@pytest.mark.asyncio
async def test_production_rate_limiter_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENV", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(redis_limiter, "get_rate_limit_redis_client", _unavailable_client)

    result = await RedisFixedWindowRateLimiter().consume(
        "login:ip:203.0.113.5",
        limit=5,
        window_seconds=300,
    )

    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after > 0


@pytest.mark.asyncio
async def test_development_rate_limiter_keeps_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENV", EnvironmentType.DEVELOPMENT)
    monkeypatch.setattr(redis_limiter, "get_rate_limit_redis_client", _unavailable_client)

    result = await RedisFixedWindowRateLimiter().consume(
        "test:development-fallback:unique",
        limit=5,
        window_seconds=300,
    )

    assert result.allowed is True
    assert result.remaining == 4
