# =================== #
#   core_queue_worker #
# =================== #

"""ARQ worker entrypoint for background jobs."""

from __future__ import annotations

from uuid import UUID

from app.config.database import AsyncSessionLocal, engine
from app.core.queue.arq import DEFAULT_EMAIL_OUTBOX_BATCH_SIZE, get_arq_redis_settings
from app.modules.bulk_imports.live_service import BulkImportLiveService
from app.modules.email_outbox.service import EmailOutboxService


async def process_email_outbox_batch(ctx: dict, batch_size: int = DEFAULT_EMAIL_OUTBOX_BATCH_SIZE) -> dict[str, int]:
    """Process one email outbox batch and enqueue the next batch when work remains."""

    safe_batch_size = min(batch_size, DEFAULT_EMAIL_OUTBOX_BATCH_SIZE)

    async with AsyncSessionLocal() as db:
        result = await EmailOutboxService.process_pending_batch(
            db=db,
            batch_size=safe_batch_size,
        )

    remaining = int(result.get("remaining") or 0)
    if remaining > 0:
        await ctx["redis"].enqueue_job("process_email_outbox_batch", safe_batch_size)

    return result


async def process_bulk_import_job(
    ctx: dict,
    job_id: str,
    tenant_id: str,
    actor_id: str,
    notify_on_completion: bool = True,
) -> dict[str, int | str]:
    """Process a confirmed bulk import job in the background."""

    _ = ctx
    async with AsyncSessionLocal() as db:
        return await BulkImportLiveService.process_confirmed_import_job(
            db=db,
            tenant_id=UUID(tenant_id),
            actor_id=UUID(actor_id),
            job_id=UUID(job_id),
            notify_on_completion=notify_on_completion,
        )


async def shutdown(ctx: dict) -> None:
    """Dispose database engine when the worker shuts down."""

    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """ARQ worker settings.

    Railway worker command example:
    arq app.core.queue.worker.WorkerSettings
    """

    redis_settings = get_arq_redis_settings()
    functions = [process_email_outbox_batch, process_bulk_import_job]
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 600
    keep_result = 300
