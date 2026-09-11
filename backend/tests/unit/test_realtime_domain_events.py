from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.modules.bulk_imports.live_service import _publish_job_event
from app.modules.bulk_imports.models import ImportJobStatus
from app.modules.student_academics.models import StudentProgressionRunStatus
from app.modules.student_academics.session_closure_service import SessionClosureService


async def test_bulk_import_event_is_actor_targeted_and_identification_only(monkeypatch):
    tenant_id = uuid4()
    actor_id = uuid4()
    job_id = uuid4()
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr("app.modules.bulk_imports.live_service.RealtimePublisher.to_actor", publish)

    await _publish_job_event(
        event_type="bulk_import.progress",
        tenant_id=tenant_id,
        actor_id=actor_id,
        import_job=SimpleNamespace(
            id=job_id,
            status=ImportJobStatus.PROCESSING,
            processed_rows=25,
            total_rows=100,
        ),
    )

    publish.assert_awaited_once_with(
        event_type="bulk_import.progress",
        actor_type="tenant_admin",
        actor_id=actor_id,
        tenant_id=tenant_id,
        data={
            "job_id": str(job_id),
            "status": "processing",
            "processed_rows": 25,
            "total_rows": 100,
        },
    )


async def test_session_progression_event_targets_initiating_admin(monkeypatch):
    tenant_id = uuid4()
    actor_id = uuid4()
    session_id = uuid4()
    run_id = uuid4()
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.modules.student_academics.session_closure_service.RealtimePublisher.to_actor",
        publish,
    )

    await SessionClosureService._publish_progression_event(
        run=SimpleNamespace(
            id=run_id,
            tenant_id=tenant_id,
            academic_session_id=session_id,
            initiated_by_admin_id=actor_id,
            status=StudentProgressionRunStatus.COMPLETED,
        ),
        event_type="academic_session.progression.completed",
    )

    assert publish.await_args.kwargs["actor_id"] == actor_id
    assert publish.await_args.kwargs["tenant_id"] == tenant_id
    assert publish.await_args.kwargs["data"]["session_id"] == str(session_id)
    assert publish.await_args.kwargs["data"]["progression_run_id"] == str(run_id)


def test_bulk_progress_is_published_once_per_committed_chunk_not_per_row():
    source = (
        Path(__file__).resolve().parents[2] / "app" / "modules" / "bulk_imports" / "live_service.py"
    ).read_text(encoding="utf-8")
    assert source.count('event_type="bulk_import.progress"') == 1
    progress_block = source.split('event_type="bulk_import.progress"', 1)[0].rsplit(
        "for chunk in", 1
    )[1]
    assert "await db.commit()" in progress_block
