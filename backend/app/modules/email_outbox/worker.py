# =========================== #
#   email_outbox_worker.py    #
# =========================== #

"""ARQ worker functions for email outbox delivery."""

from __future__ import annotations

from typing import Any

from app.config.database import AsyncSessionLocal
from app.modules.email_outbox.service import EmailOutboxService


async def process_email_outbox_batch(
    ctx: dict[str, Any],
    batch_size: int = 50,
) -> dict[str, int]:
    """Process one batch of queued emails and enqueue another batch if needed."""

    async with AsyncSessionLocal() as db:
        result = await EmailOutboxService.process_pending_batch(
            db=db,
            batch_size=batch_size,
        )

    if result["remaining"] > 0 and "redis" in ctx:
        await ctx["redis"].enqueue_job("process_email_outbox_batch", batch_size)

    return result
