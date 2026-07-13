# =================== #
#   core_queue_arq.py #
# =================== #

"""ARQ connection settings and queue-specific enqueue helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

from app.config.settings import settings


EMAIL_QUEUE_NAME = "weave:queue:email"
BULK_IMPORT_QUEUE_NAME = "weave:queue:bulk-import"

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
        username=parsed_url.username,
        password=parsed_url.password,
        ssl=parsed_url.scheme == "rediss",
    )


async def enqueue_email_outbox_batch(
    *,
    batch_size: int = DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
) -> bool:
    """Enqueue one email-outbox batch on the dedicated email queue."""

    safe_batch_size = max(
        1,
        min(int(batch_size), DEFAULT_EMAIL_OUTBOX_BATCH_SIZE),
    )

    redis = await create_pool(
        get_arq_redis_settings(),
        default_queue_name=EMAIL_QUEUE_NAME,
    )

    try:
        job = await redis.enqueue_job(
            "process_email_outbox_batch",
            safe_batch_size,
            _queue_name=EMAIL_QUEUE_NAME,
        )
    finally:
        await redis.close()

    return job is not None


async def enqueue_bulk_import_job(
    *,
    job_id: str,
    tenant_id: str,
    actor_id: str,
    notify_on_completion: bool = True,
) -> bool:
    """Enqueue one confirmed import on the dedicated bulk-import queue."""

    redis = await create_pool(
        get_arq_redis_settings(),
        default_queue_name=BULK_IMPORT_QUEUE_NAME,
    )

    try:
        job = await redis.enqueue_job(
            "process_bulk_import_job",
            job_id,
            tenant_id,
            actor_id,
            notify_on_completion,
            _queue_name=BULK_IMPORT_QUEUE_NAME,
            _job_id=f"bulk-import:{job_id}",
        )
    finally:
        await redis.close()

    # None means the same import job was already queued.
    # Treat that as safe idempotent behaviour.
    return job is not None