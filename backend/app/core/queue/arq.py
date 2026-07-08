# ================== #
#   core_queue_arq.py #
# ================== #

"""ARQ queue helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

from app.config.settings import settings


DEFAULT_EMAIL_OUTBOX_BATCH_SIZE = 20


def get_arq_redis_settings() -> RedisSettings:
    """Build ARQ Redis settings from REDIS_URL."""

    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    parsed_url = urlparse(redis_url)

    database = 0
    if parsed_url.path and parsed_url.path != "/":
        database = int(parsed_url.path.lstrip("/") or 0)

    return RedisSettings(
        host=parsed_url.hostname or "localhost",
        port=parsed_url.port or 6379,
        database=database,
        password=parsed_url.password,
        ssl=parsed_url.scheme == "rediss",
    )


async def enqueue_email_outbox_batch(*, batch_size: int = DEFAULT_EMAIL_OUTBOX_BATCH_SIZE) -> bool:
    """Enqueue a background email outbox batch job."""

    safe_batch_size = min(batch_size, DEFAULT_EMAIL_OUTBOX_BATCH_SIZE)
    redis = await create_pool(get_arq_redis_settings())
    try:
        await redis.enqueue_job("process_email_outbox_batch", safe_batch_size)
    finally:
        await redis.close()

    return True
