# ============================= #
#   bulk_import_queue_worker.py #
# ============================= #

"""Dedicated ARQ worker for confirmed bulk imports."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import app.models  # noqa: F401





from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    BULK_IMPORT_QUEUE_NAME,
    get_arq_redis_settings,
)
from app.core.queue.context import (  # noqa: E402
    reset_current_bulk_import_job_id,
    set_current_bulk_import_job_id,
)
from app.modules.bulk_imports.live_service import BulkImportLiveService  # noqa: E402


async def process_bulk_import_job(
    ctx: dict[str, Any],
    job_id: str,
    tenant_id: str,
    actor_id: str,
    notify_on_completion: bool = True,
) -> dict[str, int | str]:
    """Process one confirmed bulk-import job."""

    _ = ctx
    context_token = set_current_bulk_import_job_id(job_id)

    try:
        async with AsyncSessionLocal() as db:
            return await BulkImportLiveService.process_confirmed_import_job(
                db=db,
                tenant_id=UUID(tenant_id),
                actor_id=UUID(actor_id),
                job_id=UUID(job_id),
                notify_on_completion=notify_on_completion,
            )
    finally:
        reset_current_bulk_import_job_id(context_token)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Dispose this worker process's database engine."""

    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """Settings for the dedicated bulk-import worker."""

    redis_settings = get_arq_redis_settings()
    queue_name = BULK_IMPORT_QUEUE_NAME

    functions = [
        process_bulk_import_job,
    ]

    on_shutdown = shutdown

    # Imports are DB-heavy, so keep pilot concurrency conservative.
    max_jobs = 2

    # Allow large imports enough time to finish.
    job_timeout = 1800
    keep_result = 300

    health_check_key = f"{BULK_IMPORT_QUEUE_NAME}:health"
