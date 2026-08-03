from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.modules.bulk_imports.live_service import _job_is_stale, _terminal_result_rows
from app.modules.bulk_imports.repository import ImportJobRepository
from app.modules.bulk_imports.service import utc_now


def test_stale_import_detection_uses_last_progress_timestamp() -> None:
    job = SimpleNamespace(updated_at=utc_now(), started_at=utc_now())
    stale_metadata = {
        "background_import_started_at": (utc_now() - timedelta(hours=1)).isoformat(),
        "last_progress_at": (utc_now() - timedelta(hours=1)).isoformat(),
    }
    active_metadata = {
        "background_import_started_at": utc_now().isoformat(),
        "last_progress_at": utc_now().isoformat(),
    }

    assert _job_is_stale(job, stale_metadata) is True
    assert _job_is_stale(job, active_metadata) is False


def test_recovery_keeps_only_committed_terminal_rows() -> None:
    rows = _terminal_result_rows(
        {
            "result_rows": [
                {"row_number": 2, "status": "valid"},
                {"row_number": 3, "status": "created", "admission_number": "STU-003"},
                {"row_number": 4, "status": "failed", "error_message": "bad row"},
            ]
        }
    )

    assert [row["row_number"] for row in rows] == [3, 4]


@pytest.mark.asyncio
async def test_import_job_detail_loader_uses_current_relationships() -> None:
    class Result:
        @staticmethod
        def scalar_one_or_none():
            return None

    class Database:
        executed = False

        async def execute(self, _statement):
            self.executed = True
            return Result()

    db = Database()
    result = await ImportJobRepository.get_job_by_id(
        db,
        tenant_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        include_children=True,
    )

    assert result is None
    assert db.executed is True
