# ======================== #
#   email_queue_worker.py  #
# ======================== #

"""Dedicated ARQ worker for email-outbox delivery."""

from __future__ import annotations

from typing import Any

from arq import cron

from app.modules import import_model_modules


import_model_modules()


from app.config.database import engine  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
    EMAIL_QUEUE_NAME,
    get_arq_redis_settings,
)
from app.modules.email_outbox.worker import process_email_outbox_batch  # noqa: E402


async def poll_email_outbox(ctx: dict[str, Any]) -> dict[str, int]:
    """Periodically check the database for new or retryable outbox rows."""

    return await process_email_outbox_batch(
        ctx,
        DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    """Dispose this worker process's database engine."""

    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """Settings for the dedicated email worker."""

    redis_settings = get_arq_redis_settings()
    queue_name = EMAIL_QUEUE_NAME

    functions = [
        process_email_outbox_batch,
    ]

    # Polling prevents retryable or newly inserted outbox rows from becoming
    # stranded when no explicit ARQ trigger is present.
    cron_jobs = [
        cron(
            poll_email_outbox,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
            unique=True,
            timeout=300,
            max_tries=1,
        )
    ]

    on_shutdown = shutdown

    # Three jobs means at most three batches are active concurrently.
    # Each batch contains at most 20 rows.
    max_jobs = 3
    job_timeout = 300
    keep_result = 60

    health_check_key = f"{EMAIL_QUEUE_NAME}:health"