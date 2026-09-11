from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.report_cards.bulk_schemas import ReportCardBulkReopenRequest
from app.modules.report_cards.bulk_service import BulkReportCardService
from app.modules.report_cards.models import ReportCardStatus


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
async def test_bulk_report_card_reopen_skips_superseded_history() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)
    current = SimpleNamespace(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
        status=ReportCardStatus.ARCHIVED,
        superseded_at=None,
        published_at=None,
        published_by=None,
    )
    historical = SimpleNamespace(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
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
            "app.modules.report_cards.bulk_service.ReportCardRepository.get_current_draft",
            new=AsyncMock(return_value=None),
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
