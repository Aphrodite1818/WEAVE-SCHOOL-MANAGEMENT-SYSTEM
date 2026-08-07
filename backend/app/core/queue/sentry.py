"""Sentry instrumentation for ARQ jobs."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
from typing import Any, cast
from uuid import UUID

from arq import Retry

from app.config.sentry import capture_exception

WorkerFunction = Callable[..., Awaitable[Any]]

_SAFE_JOB_ARGUMENTS = frozenset(
    {
        "actor_id",
        "batch_size",
        "job_id",
        "notify_on_completion",
        "run_id",
        "tenant_id",
    }
)


def _context_value(value: Any) -> Any:
    """Convert ARQ context values into Sentry-safe values."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if value is None or isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    return str(value)


def _build_job_context(
    function: WorkerFunction,
    ctx: dict[str, Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Build safe job metadata without exposing arbitrary arguments."""

    context = {
        "arq_job_id": _context_value(ctx.get("job_id")),
        "job_try": _context_value(ctx.get("job_try")),
        "enqueue_time": _context_value(ctx.get("enqueue_time")),
    }

    try:
        bound = inspect.signature(function).bind_partial(
            ctx,
            *args,
            **kwargs,
        )
    except (TypeError, ValueError):
        return context

    for name, value in bound.arguments.items():
        if name not in _SAFE_JOB_ARGUMENTS:
            continue

        # ARQ also uses job_id internally. Distinguish a business
        # job identifier such as a bulk-import UUID.
        context_name = "business_job_id" if name == "job_id" else name

        context[context_name] = _context_value(value)

    return context


def capture_worker_exceptions(
    *,
    queue_name: str,
) -> Callable[[WorkerFunction], WorkerFunction]:
    """Capture unexpected failures while preserving ARQ behaviour."""

    def decorator(
        function: WorkerFunction,
    ) -> WorkerFunction:
        @wraps(function)
        async def wrapped(
            ctx: dict[str, Any],
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            try:
                return await function(
                    ctx,
                    *args,
                    **kwargs,
                )

            except asyncio.CancelledError:
                # Expected during worker shutdown.
                raise

            except Retry:
                # Retry is an ARQ control-flow instruction, not an
                # application incident.
                raise

            except Exception as exc:
                capture_exception(
                    exc,
                    tags={
                        "error_boundary": "arq",
                        "queue": queue_name,
                        "job_name": function.__name__,
                    },
                    contexts={
                        "arq_job": _build_job_context(
                            function,
                            ctx,
                            args,
                            kwargs,
                        )
                    },
                )

                # Always re-raise so ARQ marks the job failed and
                # preserves its existing retry semantics.
                raise

        return cast(
            WorkerFunction,
            wrapped,
        )

    return decorator
