"""Generation orchestration tests for the canonical report-card service."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest

from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardGenerateRequest,
    ReportCardResponse,
)
from app.modules.report_cards.service import ReportCardService
from app.modules.students.repository import StudentRepository
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
async def test_single_generate_dispatches_to_authoritative_student_path(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    session_id = uuid.uuid4()
    term_id = uuid.uuid4()
    actor = TenantAdmin(tenant_id=tenant_id)
    actor.id = uuid.uuid4()
    expected = ReportCardResponse.model_construct(id=uuid.uuid4())
    generate_one = AsyncMock(return_value=expected)
    monkeypatch.setattr(ReportCardService, "generate_for_student", generate_one)

    payload = ReportCardGenerateRequest(
        student_id=student_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        apply_default_principal_template=True,
    )

    result = await ReportCardService.generate(SimpleNamespace(), actor, payload)

    assert result is expected
    generate_one.assert_awaited_once_with(
        ANY,
        actor,
        student_id=student_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        principal_comment=None,
        principal_template_id=None,
        apply_default_principal_template=True,
    )


@pytest.mark.asyncio
async def test_bulk_generate_uses_canonical_student_generation_and_refreshes_positions_once(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    session_id = uuid.uuid4()
    term_id = uuid.uuid4()
    student_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    actor = TenantAdmin(tenant_id=tenant_id)
    actor.id = uuid.uuid4()
    payload = ReportCardGenerateRequest(
        class_id=class_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        apply_default_principal_template=True,
    )

    students = [SimpleNamespace(id=student_id) for student_id in student_ids]
    generated_cards = [
        ReportCardResponse.model_construct(id=uuid.uuid4()) for _ in student_ids
    ]
    generate_one = AsyncMock(side_effect=generated_cards)
    apply_positions = AsyncMock()
    get_card = AsyncMock(side_effect=generated_cards)

    monkeypatch.setattr(
        StudentRepository,
        "list_students",
        AsyncMock(return_value=(students, len(students))),
    )
    monkeypatch.setattr(ReportCardService, "generate_for_student", generate_one)
    monkeypatch.setattr(ReportCardService, "_apply_class_positions", apply_positions)
    monkeypatch.setattr(ReportCardService, "get", get_card)

    db = SimpleNamespace(commit=AsyncMock())
    result = await ReportCardService.generate(db, actor, payload)

    assert isinstance(result, ReportCardBulkGenerateResponse)
    assert len(result.generated) == len(student_ids)
    assert result.skipped == []
    assert generate_one.await_count == len(student_ids)
    assert all(call.kwargs["commit"] is False for call in generate_one.await_args_list)
    assert all(
        call.kwargs["apply_default_principal_template"] is True
        for call in generate_one.await_args_list
    )
    apply_positions.assert_awaited_once_with(
        db,
        tenant_id,
        class_id,
        session_id,
        term_id,
    )
    db.commit.assert_awaited_once()
    assert get_card.await_count == len(student_ids)


def test_bulk_generation_rejects_one_manual_or_template_principal_comment() -> None:
    base = {
        "class_id": uuid.uuid4(),
        "academic_session_id": uuid.uuid4(),
        "academic_term_id": uuid.uuid4(),
    }

    with pytest.raises(ValueError, match="grade defaults"):
        ReportCardGenerateRequest(
            **base,
            principal_comment="One sentence for the entire class.",
        )

    with pytest.raises(ValueError, match="grade defaults"):
        ReportCardGenerateRequest(
            **base,
            principal_template_id=uuid.uuid4(),
        )
