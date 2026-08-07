from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.report_cards.bulk_schemas import ReportCardBulkReopenRequest
from app.modules.report_cards.bulk_service import BulkReportCardService
from app.modules.report_cards.models import ReportCardStatus
from app.modules.student_academics.bulk_results_router import (
    BulkResultLifecycleService,
    TeacherBulkSubmitRequest,
)
from app.modules.student_academics.models import AcademicResultStatus


class _Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeDb:
    def __init__(self) -> None:
        self.commit = AsyncMock()

    def begin_nested(self) -> _Savepoint:
        return _Savepoint()


@pytest.mark.asyncio
async def test_teacher_bulk_submit_processes_complete_drafts_and_skips_incomplete() -> None:
    tenant_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    complete = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=AcademicResultStatus.DRAFT,
        test_score=10,
        assessment_score=15,
        exam_score=50,
    )
    incomplete = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=AcademicResultStatus.DRAFT,
        test_score=10,
        assessment_score=None,
        exam_score=50,
    )
    actor = SimpleNamespace(id=teacher_id, tenant_id=tenant_id)
    payload = TeacherBulkSubmitRequest(
        class_id=uuid.uuid4(),
        teacher_assignment_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
        confirmation="BULK_SUBMIT_RESULTS",
    )
    db = _FakeDb()

    with (
        patch.object(
            BulkResultLifecycleService,
            "_validate_period",
            new=AsyncMock(),
        ),
        patch.object(
            BulkResultLifecycleService,
            "_load_scope",
            new=AsyncMock(return_value=[complete, incomplete]),
        ) as load_scope,
        patch(
            "app.modules.student_academics.bulk_results_router.StudentAcademicService._apply_result_lifecycle_metadata"
        ),
        patch(
            "app.modules.student_academics.bulk_results_router.StudentAcademicRepository.upsert_result",
            new=AsyncMock(),
        ) as upsert_result,
        patch.object(
            BulkResultLifecycleService,
            "_audit",
            new=AsyncMock(),
        ) as audit,
    ):
        response = await BulkResultLifecycleService.teacher_submit(
            db,
            actor,
            payload,
        )

    assert response.matched == 2
    assert response.processed == 1
    assert len(response.skipped) == 1
    assert response.skipped[0].id == incomplete.id
    assert complete.status == AcademicResultStatus.SUBMITTED
    assert incomplete.status == AcademicResultStatus.DRAFT
    load_scope.assert_awaited_once_with(
        db,
        tenant_id=tenant_id,
        payload=payload,
        result_status=AcademicResultStatus.DRAFT,
        teacher_id=teacher_id,
    )
    upsert_result.assert_awaited_once_with(db, complete)
    audit.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_report_card_reopen_skips_superseded_history() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)
    current = SimpleNamespace(
        id=uuid.uuid4(),
        status=ReportCardStatus.ARCHIVED,
        superseded_at=None,
        published_at=SimpleNamespace(),
        published_by=uuid.uuid4(),
    )
    historical = SimpleNamespace(
        id=uuid.uuid4(),
        status=ReportCardStatus.ARCHIVED,
        superseded_at=SimpleNamespace(),
        published_at=SimpleNamespace(),
        published_by=uuid.uuid4(),
    )
    payload = ReportCardBulkReopenRequest(
        class_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
        confirmation="BULK_REOPEN_REPORT_CARDS",
        reason="Correct report-card comments",
    )
    db = _FakeDb()

    with (
        patch.object(
            BulkReportCardService,
            "_scope_cards",
            new=AsyncMock(return_value=[current, historical]),
        ),
        patch(
            "app.modules.report_cards.bulk_service.ReportCardRepository.save",
            new=AsyncMock(),
        ) as save,
        patch.object(
            BulkReportCardService,
            "_audit",
            new=AsyncMock(),
        ) as audit,
    ):
        response = await BulkReportCardService.reopen(db, actor, payload)

    assert response.matched == 2
    assert response.processed == 1
    assert len(response.skipped) == 1
    assert response.skipped[0].id == historical.id
    assert current.status == ReportCardStatus.DRAFT
    assert current.published_at is None
    assert current.published_by is None
    assert historical.status == ReportCardStatus.ARCHIVED
    save.assert_awaited_once_with(db, current)
    audit.assert_awaited_once()
    db.commit.assert_awaited_once()
