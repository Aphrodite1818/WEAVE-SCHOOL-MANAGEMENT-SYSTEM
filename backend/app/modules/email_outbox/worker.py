# =========================== #
#   email_outbox_worker.py    #
# =========================== #

"""ARQ job functions for email-outbox delivery."""

from __future__ import annotations

from typing import Any

from app.config.database import AsyncSessionLocal
from app.core.queue.arq import (
    DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
    GENERAL_QUEUE_NAME,
)
from app.modules.email_outbox.service import EmailOutboxService
from app.core.queue.sentry import capture_worker_exceptions



@capture_worker_exceptions(queue_name=GENERAL_QUEUE_NAME)
async def process_email_outbox_batch(
    ctx: dict[str, Any],
    batch_size: int = DEFAULT_EMAIL_OUTBOX_BATCH_SIZE,
) -> dict[str, int]:
    """Claim and send one bounded batch of pending outbox emails."""

    safe_batch_size = max(
        1,
        min(int(batch_size), DEFAULT_EMAIL_OUTBOX_BATCH_SIZE),
    )

    async with AsyncSessionLocal() as db:
        result = await EmailOutboxService.process_pending_batch(
            db=db,
            batch_size=safe_batch_size,
        )

    remaining = int(result.get("remaining") or 0)
    redis = ctx.get("redis")

    if remaining > 0 and redis is not None:
        await redis.enqueue_job(
            "process_email_outbox_batch",
            safe_batch_size,
            _queue_name=GENERAL_QUEUE_NAME,
            _defer_by=1,
        )

    return result
