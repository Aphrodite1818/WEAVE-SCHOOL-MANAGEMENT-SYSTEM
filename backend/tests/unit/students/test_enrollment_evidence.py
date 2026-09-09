"""Regression tests for enrollment evidence checks used by lifecycle operations."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.students.enrollment_evidence import StudentEnrollmentEvidenceService


@pytest.mark.asyncio
async def test_segment_dependency_counts_returns_all_evidence_counts() -> None:
    enrollment = SimpleNamespace(
        student_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
    )
    enrollment_result = SimpleNamespace(scalar_one_or_none=lambda: enrollment)
    count_results = [
        SimpleNamespace(scalar_one=lambda count=count: count)
        for count in (2, 3, 4, 5, 6, 7)
    ]
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[enrollment_result, *count_results])
    )

    counts = await StudentEnrollmentEvidenceService.segment_dependency_counts(
        db,
        tenant_id=uuid.uuid4(),
        enrollment_id=uuid.uuid4(),
        on_or_after=date.today(),
    )

    assert counts == {
        "attendance": 2,
        "results": 3,
        "teacher_comments": 4,
        "report_cards": 6,
        "cbt_results": 7,
        "progression": 5,
    }
    assert db.execute.await_count == 7
