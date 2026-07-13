"""Context shared by background jobs running inside one ARQ task."""

from __future__ import annotations

from contextvars import ContextVar, Token


_current_bulk_import_job_id: ContextVar[str | None] = ContextVar(
    "current_bulk_import_job_id",
    default=None,
)


def get_current_bulk_import_job_id() -> str | None:
    """Return the bulk-import job currently creating related records."""

    return _current_bulk_import_job_id.get()


def set_current_bulk_import_job_id(job_id: str) -> Token[str | None]:
    """Bind one bulk-import job ID to the current asynchronous task."""

    return _current_bulk_import_job_id.set(str(job_id))


def reset_current_bulk_import_job_id(token: Token[str | None]) -> None:
    """Restore the previous bulk-import job context."""

    _current_bulk_import_job_id.reset(token)
