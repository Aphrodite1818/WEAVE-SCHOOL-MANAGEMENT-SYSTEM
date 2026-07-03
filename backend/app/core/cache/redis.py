#==========================#
#        core.redis        #
#==========================#
"""this file is responsible for redis cache connection and operations"""

from __future__ import annotations

from redis.asyncio import Redis

from app.config.logging import get_logger
from app.config.settings import settings


logger = get_logger(__name__)
_redis_client: Redis | None = None


async def connect_redis() -> None:
    """
    Create and verify the Redis connection.

    This should run once when the FastAPI app starts.
    """

    global _redis_client

    if not settings.CACHE_ENABLED:
        logger.info("Cache is disabled. Redis connection skipped.")
        return

    if not settings.REDIS_URL:
        logger.warning("Cache enabled but Redis URL is not set. Redis connection skipped.")
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
    except Exception:
        logger.error("Failed to connect to Redis. Please check the Redis server and configuration.")
        await close_redis()


def get_redis() -> Redis | None:
    """
    Return the active Redis client.

    Returns None when cache is disabled or Redis failed to connect.
    """
    return _redis_client


async def close_redis() -> None:
    """
    Close the Redis connection.

    This should run once when the FastAPI app shuts down.
    """
    global _redis_client

    if _redis_client is None:
        return

    await _redis_client.aclose()
    _redis_client = None
    logger.info("Redis connection closed.")


async def redis_health_check() -> bool:
    """
    Check the health of the Redis connection.

    Returns True if Redis is healthy, False otherwise.
    """
    if _redis_client is None:
        logger.warning("Redis client is not initialized.")
        return False

    try:
        await _redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
