"""Tests for ARQ Sentry exception boundaries."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from arq import Retry

from app.core.queue import sentry as queue_sentry


@pytest.mark.asyncio
async def test_worker_wrapper_returns_success_result() -> None:
    @queue_sentry.capture_worker_exceptions(
        queue_name="weave:general"
    )
    async def successful_job(
        ctx: dict[str, Any],
        tenant_id: str,
    ) -> str:
        _ = ctx
        return tenant_id

    result = await successful_job(
        {
            "job_id": "arq-1",
            "job_try": 1,
        },
        "tenant-1",
    )

    assert result == "tenant-1"
    assert successful_job.__name__ == "successful_job"


@pytest.mark.asyncio
async def test_unexpected_worker_error_is_captured_and_reraised(
    monkeypatch,
) -> None:
    captured: list[dict[str, Any]] = []

    def capture(
        exc: BaseException,
        **kwargs: Any,
    ) -> None:
        captured.append(
            {
                "exception": exc,
                **kwargs,
            }
        )

    monkeypatch.setattr(
        queue_sentry,
        "capture_exception",
        capture,
    )

    @queue_sentry.capture_worker_exceptions(
        queue_name="weave:heavy"
    )
    async def failing_job(
        ctx: dict[str, Any],
        job_id: str,
        tenant_id: str,
        actor_id: str,
    ) -> None:
        _ = ctx
        raise ValueError("worker failed")

    with pytest.raises(
        ValueError,
        match="worker failed",
    ):
        await failing_job(
            {
                "job_id": "arq-job-1",
                "job_try": 2,
                "enqueue_time": (
                    "2026-08-06T22:00:00+00:00"
                ),
            },
            "bulk-import-1",
            "tenant-1",
            "actor-1",
        )

    assert len(captured) == 1

    assert captured[0]["tags"] == {
        "error_boundary": "arq",
        "queue": "weave:heavy",
        "job_name": "failing_job",
    }

    assert captured[0]["contexts"]["arq_job"] == {
        "arq_job_id": "arq-job-1",
        "job_try": 2,
        "enqueue_time": (
            "2026-08-06T22:00:00+00:00"
        ),
        "business_job_id": "bulk-import-1",
        "tenant_id": "tenant-1",
        "actor_id": "actor-1",
    }


@pytest.mark.asyncio
async def test_retry_is_not_reported_as_an_incident(
    monkeypatch,
) -> None:
    captured: list[BaseException] = []

    monkeypatch.setattr(
        queue_sentry,
        "capture_exception",
        lambda exc, **kwargs: captured.append(exc),
    )

    @queue_sentry.capture_worker_exceptions(
        queue_name="weave:general"
    )
    async def retrying_job(
        ctx: dict[str, Any],
    ) -> None:
        _ = ctx
        raise Retry(defer=1)

    with pytest.raises(Retry):
        await retrying_job(
            {
                "job_id": "arq-2",
                "job_try": 1,
            }
        )

    assert captured == []


@pytest.mark.asyncio
async def test_shutdown_cancellation_is_not_reported(
    monkeypatch,
) -> None:
    captured: list[BaseException] = []

    monkeypatch.setattr(
        queue_sentry,
        "capture_exception",
        lambda exc, **kwargs: captured.append(exc),
    )

    @queue_sentry.capture_worker_exceptions(
        queue_name="weave:general"
    )
    async def cancelled_job(
        ctx: dict[str, Any],
    ) -> None:
        _ = ctx
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await cancelled_job(
            {
                "job_id": "arq-3",
                "job_try": 1,
            }
        )

    assert captured == []