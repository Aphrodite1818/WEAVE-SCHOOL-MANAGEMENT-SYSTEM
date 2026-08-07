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


def _build_redis_client() -> Redis | None:
    if not settings.REDIS_URL:
        return None
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )


async def connect_redis() -> None:
    """Verify Redis and retain a shared client when caching is enabled."""

    global _redis_client

    client = _build_redis_client()
    if client is None:
        message = "REDIS_URL is not set."
        if settings.is_production_like:
            raise RuntimeError(message)
        logger.warning(message)
        return

    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        logger.exception("Failed to connect to Redis.")
        if settings.is_production_like:
            raise RuntimeError(
                "Redis is unavailable during application startup."
            ) from exc
        return

    if settings.CACHE_ENABLED:
        _redis_client = client
        logger.info("Successfully connected to Redis cache.")
        return

    await client.aclose()
    logger.info("Redis verified; shared application cache is disabled.")


async def create_redis_health_client() -> Redis | None:
    """Return a temporary Redis client for readiness checks."""

    return _build_redis_client()


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
