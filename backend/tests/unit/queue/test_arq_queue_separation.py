from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.queue import arq as arq_queue
from app.core.queue.bulk_import_worker import WorkerSettings as BulkImportWorkerSettings
from app.core.queue.context import (
    reset_current_bulk_import_job_id,
    set_current_bulk_import_job_id,
)
from app.core.queue.email_worker import WorkerSettings as EmailWorkerSettings
from app.modules.email_outbox.service import resolve_outbox_metadata


def test_workers_listen_to_different_queues() -> None:
    assert EmailWorkerSettings.queue_name == arq_queue.EMAIL_QUEUE_NAME
    assert BulkImportWorkerSettings.queue_name == arq_queue.BULK_IMPORT_QUEUE_NAME
    assert EmailWorkerSettings.queue_name != BulkImportWorkerSettings.queue_name


def test_bulk_import_metadata_contains_active_import_job_id() -> None:
    import_job_id = str(uuid4())
    token = set_current_bulk_import_job_id(import_job_id)

    try:
        metadata = resolve_outbox_metadata(
            {
                "source": "bulk_import",
                "actor_type": "parent",
                "actor_id": str(uuid4()),
            }
        )
    finally:
        reset_current_bulk_import_job_id(token)

    assert metadata["import_job_id"] == import_job_id


def test_non_import_email_metadata_is_not_modified() -> None:
    import_job_id = str(uuid4())
    token = set_current_bulk_import_job_id(import_job_id)

    try:
        metadata = resolve_outbox_metadata({"source": "password_reset"})
    finally:
        reset_current_bulk_import_job_id(token)

    assert "import_job_id" not in metadata


@pytest.mark.asyncio
async def test_email_jobs_use_email_queue(monkeypatch) -> None:
    redis = SimpleNamespace(
        enqueue_job=AsyncMock(return_value=object()),
        close=AsyncMock(),
    )

    monkeypatch.setattr(
        arq_queue,
        "create_pool",
        AsyncMock(return_value=redis),
    )

    queued = await arq_queue.enqueue_email_outbox_batch(batch_size=20)

    assert queued is True
    redis.enqueue_job.assert_awaited_once_with(
        "process_email_outbox_batch",
        20,
        _queue_name=arq_queue.EMAIL_QUEUE_NAME,
    )


@pytest.mark.asyncio
async def test_import_jobs_use_import_queue(monkeypatch) -> None:
    redis = SimpleNamespace(
        enqueue_job=AsyncMock(return_value=object()),
        close=AsyncMock(),
    )

    monkeypatch.setattr(
        arq_queue,
        "create_pool",
        AsyncMock(return_value=redis),
    )

    import_job_id = str(uuid4())
    tenant_id = str(uuid4())
    actor_id = str(uuid4())

    queued = await arq_queue.enqueue_bulk_import_job(
        job_id=import_job_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
    )

    assert queued is True
    redis.enqueue_job.assert_awaited_once_with(
        "process_bulk_import_job",
        import_job_id,
        tenant_id,
        actor_id,
        True,
        _queue_name=arq_queue.BULK_IMPORT_QUEUE_NAME,
        _job_id=f"bulk-import:{import_job_id}",
    )
