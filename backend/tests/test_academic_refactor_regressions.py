from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.modules.student_academics.lifecycle_repository import StudentProgressionItemRepository
from app.modules.student_academics.models import (
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
)


@pytest.mark.asyncio
async def test_progression_item_retry_updates_existing_logical_item(monkeypatch):
    run_id = uuid.uuid4()
    student_id = uuid.uuid4()
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=existing_id,
        tenant_id=uuid.uuid4(),
        progression_run_id=run_id,
        student_id=student_id,
        from_enrollment_id=None,
        to_enrollment_id=None,
        from_class_id=None,
        to_class_id=None,
        action=StudentProgressionItemAction.SKIP,
        status=StudentProgressionItemStatus.FAILED,
        reason="first failure",
        processed_at=None,
    )
    monkeypatch.setattr(
        StudentProgressionItemRepository,
        "get_by_run_and_student",
        AsyncMock(return_value=existing),
    )
    db = SimpleNamespace(add=lambda item: None, flush=AsyncMock())
    incoming = StudentProgressionItem(
        tenant_id=existing.tenant_id,
        progression_run_id=run_id,
        student_id=student_id,
        action=StudentProgressionItemAction.PROMOTE,
        status=StudentProgressionItemStatus.PROMOTED,
        reason="retry succeeded",
    )

    saved = await StudentProgressionItemRepository.add(db, incoming)

    assert saved is existing
    assert saved.id == existing_id
    assert saved.status == StudentProgressionItemStatus.PROMOTED
    assert saved.reason == "retry succeeded"
    db.flush.assert_awaited_once()


def test_current_period_partial_indexes_cover_closing_state():
    from app.modules.student_academics.models import AcademicSession, AcademicTerm

    session_index = next(
        item
        for item in AcademicSession.__table__.indexes
        if item.name == "uq_academic_sessions_current_per_tenant"
    )
    term_index = next(
        item
        for item in AcademicTerm.__table__.indexes
        if item.name == "uq_academic_terms_current_per_tenant"
    )
    assert "closing" in str(session_index.dialect_options["postgresql"]["where"])
    assert "closing" in str(term_index.dialect_options["postgresql"]["where"])
