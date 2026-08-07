"""ARQ worker for lightweight recurring and operational jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from arq import cron

import app.models  # noqa: F401

from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.config.sentry import flush_sentry, initialize_sentry  # noqa: E402
from app.core.queue.sentry import capture_worker_exceptions  # noqa: E402
from app.config.logging import get_logger  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
    GENERAL_QUEUE_NAME,
    get_arq_redis_settings,
)
from app.modules.attendance.repository import AttendanceRepository  # noqa: E402
from app.modules.email_outbox.worker import process_email_outbox_batch  # noqa: E402
from app.modules.subscriptions.plan_change_service import (  # noqa: E402
    SubscriptionPlanChangeService,
)
from app.modules.subscriptions.service import (  # noqa: E402
    SubscriptionLifecycleService,
)

logger = get_logger(__name__)
SUBSCRIPTION_RECONCILIATION_SUCCESS_KEY = (
    "weave:ops:subscription-reconciliation:last-success"
)


async def poll_email_outbox(ctx: dict[str, Any]) -> dict[str, int]:
    """Periodically process pending and retryable email-outbox rows."""

    return await process_email_outbox_batch(ctx, DEFAULT_EMAIL_OUTBOX_BATCH_SIZE)


@capture_worker_exceptions(queue_name=GENERAL_QUEUE_NAME)
async def process_attendance_retention_job(
    ctx: dict[str, Any],
    tenant_id: str | None = None,
) -> dict[str, int]:
    """Purge expired raw location evidence without deleting attendance rows."""

    _ = ctx
    parsed_tenant_id = uuid.UUID(tenant_id) if tenant_id else None
    async with AsyncSessionLocal() as db:
        result = await AttendanceRepository.purge_expired_location_evidence(
            db,
            tenant_id=parsed_tenant_id,
        )
        await db.commit()

    logger.info(
        "attendance.retention.completed",
        extra={"tenant_id": tenant_id, **result},
    )
    return result


async def poll_attendance_retention(ctx: dict[str, Any]) -> dict[str, int]:
    return await process_attendance_retention_job(ctx)


@capture_worker_exceptions(queue_name=GENERAL_QUEUE_NAME)
async def process_subscription_lifecycle_job(
    ctx: dict[str, Any],
) -> dict[str, int]:
    """Advance expired billing periods and due scheduled downgrades."""

    async with AsyncSessionLocal() as db:
        lifecycle = await SubscriptionLifecycleService.sync_expired_subscriptions(db=db)
        plan_changes = await SubscriptionPlanChangeService.sync_due_changes(db=db)
        result = {
            **lifecycle,
            "plan_changes_awaiting_payment": plan_changes["awaiting_payment"],
            "plan_changes_blocked": plan_changes["blocked"],
        }

    completed_at = datetime.now(timezone.utc).isoformat()
    redis = ctx.get("redis")
    if redis is not None:
        await redis.set(SUBSCRIPTION_RECONCILIATION_SUCCESS_KEY, completed_at)

    logger.info(
        "subscription.reconciliation.completed",
        extra={"completed_at": completed_at, **result},
    )
    return result


async def poll_subscription_lifecycle(ctx: dict[str, Any]) -> dict[str, int]:
    return await process_subscription_lifecycle_job(ctx)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize optional monitoring for this worker process."""

    _ = ctx

    initialize_sentry(
        service="worker-general",
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    """Dispose the worker's database and monitoring resources."""

    _ = ctx

    try:
        await engine.dispose()
    finally:
        await flush_sentry()


class WorkerSettings:
    """Settings for lightweight and recurring background work."""

    redis_settings = get_arq_redis_settings()
    queue_name = GENERAL_QUEUE_NAME
    functions = [
        process_email_outbox_batch,
        process_attendance_retention_job,
        process_subscription_lifecycle_job,
    ]
    cron_jobs = [
        cron(
            poll_email_outbox,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
            unique=True,
            timeout=300,
            max_tries=1,
        ),
        cron(
            poll_attendance_retention,
            hour={1},
            minute=15,
            run_at_startup=False,
            unique=True,
            timeout=300,
            max_tries=1,
        ),
        cron(
            poll_subscription_lifecycle,
            minute=7,
            run_at_startup=True,
            unique=True,
            timeout=300,
            max_tries=2,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 3
    job_timeout = 300
    keep_result = 3600
    health_check_key = f"{GENERAL_QUEUE_NAME}:health"
