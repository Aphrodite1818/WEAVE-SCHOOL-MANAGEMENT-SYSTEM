from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.ranking_policy import (
    _dense_rank,
    refresh_draft_rank_from_authoritative_results,
)
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.students.repository import StudentRepository


def test_dense_rank_preserves_ties() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()

    ranks = _dense_rank(
        [
            (first, Decimal("90")),
            (second, Decimal("90")),
            (third, Decimal("75")),
        ]
    )

    assert ranks[first] == 1
    assert ranks[second] == 1
    assert ranks[third] == 2


@pytest.mark.asyncio
async def test_draft_rank_uses_all_ready_classmates_not_generated_report_rows(monkeypatch) -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    first_id, target_id, incomplete_id = uuid4(), uuid4(), uuid4()
    students = [
        SimpleNamespace(id=first_id),
        SimpleNamespace(id=target_id),
        SimpleNamespace(id=incomplete_id),
    ]
    card = SimpleNamespace(
        status=ReportCardStatus.DRAFT,
        class_id=class_id,
        tenant_id=tenant_id,
        student_id=target_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        position=None,
        position_out_of=None,
    )

    async def readiness(_db, *, student_id, **_kwargs):
        if student_id == first_id:
            return True, Decimal("91"), SimpleNamespace(id=uuid4(), grade="A")
        if student_id == target_id:
            return True, Decimal("82"), SimpleNamespace(id=uuid4(), grade="A")
        return False, None, None

    list_students = AsyncMock(return_value=(students, len(students)))
    save = AsyncMock(return_value=card)
    monkeypatch.setattr(StudentRepository, "list_for_tenant", list_students)
    monkeypatch.setattr(
        ReportCommentService,
        "_academic_readiness",
        AsyncMock(side_effect=readiness),
    )
    monkeypatch.setattr(ReportCardRepository, "save", save)

    result = await refresh_draft_rank_from_authoritative_results(
        SimpleNamespace(),
        card=card,
    )

    assert result is card
    assert card.position == 2
    assert card.position_out_of == 2
    list_students.assert_awaited_once_with(
        db=pytest.ANY if False else list_students.await_args.kwargs["db"],
        tenant_id=tenant_id,
        class_id=class_id,
        limit=500,
    )
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_published_rank_snapshot_is_never_recomputed(monkeypatch) -> None:
    card = SimpleNamespace(
        status=ReportCardStatus.PUBLISHED,
        position=3,
        position_out_of=32,
    )
    list_students = AsyncMock()
    save = AsyncMock()
    monkeypatch.setattr(StudentRepository, "list_for_tenant", list_students)
    monkeypatch.setattr(ReportCardRepository, "save", save)

    result = await refresh_draft_rank_from_authoritative_results(
        SimpleNamespace(),
        card=card,
    )

    assert result is card
    assert card.position == 3
    assert card.position_out_of == 32
    list_students.assert_not_awaited()
    save.assert_not_awaited()
