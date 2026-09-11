from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.cbt.enums import CBTResultIngestionStatus
from app.modules.cbt.results.models import _new_ingestion_reference
from app.modules.cbt.results.schemas import CBTResultBulkRequest, CBTResultBulkScoreItem
from app.modules.cbt.results.service import CBTResultIngestionService
from app.modules.report_cards.service import ReportCardService


def _payload(*, score_a: str = "35.00", reverse: bool = False) -> CBTResultBulkRequest:
    student_a = uuid4()
    student_b = uuid4()
    items = [
        CBTResultBulkScoreItem(student_id=student_a, score=Decimal(score_a)),
        CBTResultBulkScoreItem(student_id=student_b, score=Decimal("42.50")),
    ]
    if reverse:
        items.reverse()
    return CBTResultBulkRequest(
        batch_id=uuid4(),
        source_exam_id=uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        academic_level_id=uuid4(),
        curriculum_subject_id=uuid4(),
        assessment_component_id=uuid4(),
        exam_date=date(2026, 9, 8),
        scores=items,
    )


def test_result_ingestion_status_contract_matches_service_terminal_states() -> None:
    assert {item.value for item in CBTResultIngestionStatus} == {
        "processing",
        "completed",
        "completed_with_rejections",
        "rejected",
        "failed",
    }


def test_ingestion_reference_is_human_facing_and_not_a_raw_uuid() -> None:
    first = _new_ingestion_reference()
    second = _new_ingestion_reference()

    assert first.startswith("CBT-")
    assert len(first) <= 32
    assert first != second
    assert "-" in first


def test_request_hash_is_score_order_independent() -> None:
    batch_id = uuid4()
    exam_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    level_id = uuid4()
    subject_id = uuid4()
    component_id = uuid4()
    student_a = uuid4()
    student_b = uuid4()

    common = dict(
        batch_id=batch_id,
        source_exam_id=exam_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        academic_level_id=level_id,
        curriculum_subject_id=subject_id,
        assessment_component_id=component_id,
        exam_date=date(2026, 9, 8),
    )
    first = CBTResultBulkRequest(
        **common,
        scores=[
            CBTResultBulkScoreItem(student_id=student_a, score=Decimal("35")),
            CBTResultBulkScoreItem(student_id=student_b, score=Decimal("42.50")),
        ],
    )
    second = CBTResultBulkRequest(
        **common,
        scores=[
            CBTResultBulkScoreItem(student_id=student_b, score=Decimal("42.500")),
            CBTResultBulkScoreItem(student_id=student_a, score=Decimal("35.00")),
        ],
    )

    assert CBTResultIngestionService._request_hash(
        first
    ) == CBTResultIngestionService._request_hash(second)


def test_request_hash_changes_when_score_changes() -> None:
    payload = _payload()
    changed = payload.model_copy(
        update={
            "scores": [
                payload.scores[0].model_copy(update={"score": Decimal("36.00")}),
                payload.scores[1],
            ]
        }
    )

    assert CBTResultIngestionService._request_hash(
        payload
    ) != CBTResultIngestionService._request_hash(changed)


def test_bulk_request_rejects_duplicate_student() -> None:
    student_id = uuid4()
    with pytest.raises(ValidationError, match="Each student may appear only once"):
        CBTResultBulkRequest(
            batch_id=uuid4(),
            source_exam_id=uuid4(),
            academic_session_id=uuid4(),
            academic_term_id=uuid4(),
            academic_level_id=uuid4(),
            curriculum_subject_id=uuid4(),
            assessment_component_id=uuid4(),
            exam_date=date(2026, 9, 8),
            scores=[
                CBTResultBulkScoreItem(student_id=student_id, score=Decimal("20")),
                CBTResultBulkScoreItem(student_id=student_id, score=Decimal("25")),
            ],
        )


@pytest.mark.asyncio
async def test_applied_cbt_results_invalidate_each_report_context_once(monkeypatch) -> None:
    tenant_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    first_student = uuid4()
    second_student = uuid4()
    invalidate = AsyncMock()
    monkeypatch.setattr(
        ReportCardService,
        "mark_outdated_for_score_change",
        invalidate,
    )

    await CBTResultIngestionService._invalidate_report_derivations(
        SimpleNamespace(),
        tenant_id=tenant_id,
        results=[
            SimpleNamespace(
                student_id=first_student,
                academic_session_id=session_id,
                academic_term_id=term_id,
            ),
            SimpleNamespace(
                student_id=first_student,
                academic_session_id=session_id,
                academic_term_id=term_id,
            ),
            SimpleNamespace(
                student_id=second_student,
                academic_session_id=session_id,
                academic_term_id=term_id,
            ),
        ],
    )

    assert invalidate.await_count == 2
    invalidate.assert_any_await(
        ANY,
        tenant_id,
        first_student,
        session_id,
        term_id,
    )
    invalidate.assert_any_await(
        ANY,
        tenant_id,
        second_student,
        session_id,
        term_id,
    )
