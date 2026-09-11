"""Regression tests for enrollment evidence checks used by lifecycle operations."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.students.enrollment_evidence import StudentEnrollmentEvidenceService


@pytest.mark.asyncio
async def test_segment_dependency_counts_returns_attendance_and_result_counts() -> None:
    attendance_result = SimpleNamespace(scalar_one=lambda: 2)
    score_result = SimpleNamespace(scalar_one=lambda: 3)
    db = SimpleNamespace(execute=AsyncMock(side_effect=[attendance_result, score_result]))

    counts = await StudentEnrollmentEvidenceService.segment_dependency_counts(
        db,
        tenant_id=uuid.uuid4(),
        enrollment_id=uuid.uuid4(),
        on_or_after=date.today(),
    )

    assert counts == {"attendance": 2, "results": 3}
    assert db.execute.await_count == 2
