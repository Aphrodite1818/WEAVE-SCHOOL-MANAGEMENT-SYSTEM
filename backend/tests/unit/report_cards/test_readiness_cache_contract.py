from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.modules.report_cards.cache import ReportReadinessCache
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.readiness_service import ReportReadinessService
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.curriculum_service import CurriculumResolutionService


@pytest.mark.asyncio
async def test_readiness_cache_hit_preserves_zero_percent_without_database_resolution(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    scale_id = uuid4()
    resolve_curriculum = AsyncMock()

    monkeypatch.setattr(
        ReportReadinessCache,
        "get",
        AsyncMock(
            return_value={
                "expected_count": 4,
                "locked_count": 4,
                "missing_subject_names": [],
                "performance_percentage": "0.00",
                "grading_scale_id": str(scale_id),
                "overall_grade": "F",
            }
        ),
    )
    monkeypatch.setattr(
        CurriculumResolutionService,
        "resolve_student_curriculum",
        resolve_curriculum,
    )

    snapshot = await ReportReadinessService.resolve_result_readiness(
        SimpleNamespace(),
        tenant_id=tenant_id,
        student_id=student_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
    )

    assert snapshot.complete is True
    assert snapshot.performance_percentage == Decimal("0.00")
    assert snapshot.grading_scale_id == scale_id
    assert snapshot.overall_grade == "F"
    resolve_curriculum.assert_not_awaited()


@pytest.mark.asyncio
async def test_score_change_invalidates_readiness_comments_and_report_versions(monkeypatch) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    invalidate_cache = AsyncMock()
    invalidate_comments = AsyncMock()
    mark_cards = AsyncMock()

    monkeypatch.setattr(
        ReportReadinessCache,
        "invalidate_context",
        invalidate_cache,
    )
    monkeypatch.setattr(
        ReportCommentService,
        "invalidate_for_result_change",
        invalidate_comments,
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "mark_outdated_for_student_period",
        mark_cards,
    )

    await ReportCardService.mark_outdated_for_score_change(
        SimpleNamespace(),
        tenant_id,
        student_id,
        session_id,
        term_id,
    )

    invalidate_cache.assert_awaited_once_with(
        tenant_id=tenant_id,
        student_id=student_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
    )
    invalidate_comments.assert_awaited_once_with(
        ANY,
        tenant_id=tenant_id,
        student_id=student_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
    )
    mark_cards.assert_awaited_once_with(
        ANY,
        tenant_id,
        student_id,
        session_id,
        term_id,
    )
