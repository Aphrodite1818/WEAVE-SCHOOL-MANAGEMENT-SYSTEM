"""Backward-compatible alias for the dedicated email worker."""

from app.core.queue.email_worker import (
    WorkerSettings,
    poll_email_outbox,
    process_email_outbox_batch,
)

__all__ = [
    "WorkerSettings",
    "poll_email_outbox",
    "process_email_outbox_batch",
]