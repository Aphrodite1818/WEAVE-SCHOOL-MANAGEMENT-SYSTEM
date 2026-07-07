from __future__ import annotations

from app.modules import import_model_modules


import_model_modules()

from app.core.queue.arq import get_arq_redis_settings  # noqa: E402
from app.modules.email_outbox.worker import process_email_outbox_batch  # noqa: E402


class WorkerSettings:
    functions = [process_email_outbox_batch]
    redis_settings = get_arq_redis_settings()
    max_jobs = 10
    job_timeout = 300
