# ========================== #
#        core.redis          #
# ========================== #

"""Redis cache connection and health operations."""

from __future__ import annotations

from redis.asyncio import Redis

from app.config.logging import get_logger
from app.config.settings import settings


logger = get_logger(__name__)
_redis_client: Redis | None = None


async def connect_redis() -> None:
    """Create and verify the shared Redis connection."""

    global _redis_client

    if not settings.CACHE_ENABLED:
        logger.info("Cache is disabled. Shared Redis cache connection skipped.")
        return
    if not settings.REDIS_URL:
        message = "Cache is enabled but REDIS_URL is not set."
        if settings.is_production_like:
            raise RuntimeError(message)
        logger.warning(message)
        return

    _redis_client = Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )

    try:
        await _redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as exc:
        logger.exception("Failed to connect to Redis.")
        await close_redis()
        if settings.is_production_like:
            raise RuntimeError("Redis is unavailable during application startup.") from exc


async def create_redis_health_client() -> Redis | None:
    """Return a temporary Redis client for readiness checks."""

    if not settings.REDIS_URL:
        return None
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
    )


def get_redis() -> Redis | None:
    """Return the active shared Redis client, when cache is enabled."""

    return _redis_client


async def close_redis() -> None:
    """Close the shared Redis connection."""

    global _redis_client
    if _redis_client is None:
        return

    await _redis_client.aclose()
    _redis_client = None
    logger.info("Redis connection closed.")


async def redis_health_check() -> bool:
    """Check Redis even when the optional shared cache client is disabled."""

    client = _redis_client
    temporary_client = False
    if client is None:
        client = await create_redis_health_client()
        temporary_client = client is not None
    if client is None:
        return not settings.is_production_like

    try:
        await client.ping()
        return True
    except Exception:
        logger.exception("Redis health check failed.")
        return False
    finally:
        if temporary_client:
            await client.aclose()
