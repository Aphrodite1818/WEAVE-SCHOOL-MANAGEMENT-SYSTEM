"""ARQ worker settings for background jobs."""

from __future__ import annotations

from app.core.queue.arq import get_arq_redis_settings
from app.modules.email_outbox.worker import process_email_outbox_batch


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [process_email_outbox_batch]
    redis_settings = get_arq_redis_settings()
    max_jobs = 10
    job_timeout = 300
