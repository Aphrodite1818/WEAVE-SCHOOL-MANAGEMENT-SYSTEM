"""Backward-compatible alias for the dedicated bulk-import worker."""

from app.core.queue.bulk_import_worker import (
    WorkerSettings,
    process_bulk_import_job,
)

__all__ = [
    "WorkerSettings",
    "process_bulk_import_job",
]