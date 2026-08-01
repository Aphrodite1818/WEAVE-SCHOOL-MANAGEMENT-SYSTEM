"""Dedicated ARQ worker for subscription and plan-change reconciliation."""

from __future__ import annotations

from typing import Any

from arq import cron

import app.models  # noqa: F401

from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    SUBSCRIPTION_QUEUE_NAME,
    get_arq_redis_settings,
)
from app.modules.subscriptions.plan_change_service import (  # noqa: E402
    SubscriptionPlanChangeService,
)
from app.modules.subscriptions.service import (  # noqa: E402
    SubscriptionLifecycleService,
)


async def process_subscription_lifecycle_job(
    ctx: dict[str, Any],
) -> dict[str, int]:
    """Advance expired billing periods and due scheduled downgrades."""

    _ = ctx
    async with AsyncSessionLocal() as db:
        lifecycle = await SubscriptionLifecycleService.sync_expired_subscriptions(db=db)
        plan_changes = await SubscriptionPlanChangeService.sync_due_changes(db=db)
        return {
            **lifecycle,
            "plan_changes_awaiting_payment": plan_changes["awaiting_payment"],
            "plan_changes_blocked": plan_changes["blocked"],
        }


async def poll_subscription_lifecycle(ctx: dict[str, Any]) -> dict[str, int]:
    return await process_subscription_lifecycle_job(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """Settings for the dedicated subscription lifecycle worker."""

    redis_settings = get_arq_redis_settings()
    queue_name = SUBSCRIPTION_QUEUE_NAME
    functions = [process_subscription_lifecycle_job]
    cron_jobs = [
        cron(
            poll_subscription_lifecycle,
            minute=7,
            run_at_startup=True,
            unique=True,
            timeout=300,
            max_tries=2,
        )
    ]
    on_shutdown = shutdown
    max_jobs = 1
    job_timeout = 300
    keep_result = 3600
    health_check_key = f"{SUBSCRIPTION_QUEUE_NAME}:health"
