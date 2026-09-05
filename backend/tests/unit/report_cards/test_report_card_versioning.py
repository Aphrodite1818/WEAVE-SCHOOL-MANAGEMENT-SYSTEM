from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.schemas import ReportCardGenerateRequest
from app.modules.report_cards.service import ReportCardService
from app.modules.students.repository import StudentRepository


def test_dense_rank_preserves_ties_without_mutating_published_snapshots():
    first = uuid4()
    second = uuid4()
    third = uuid4()

    ranks = ReportCardService._dense_rank(
        [(first, 90), (second, 90), (third, 75)]
    )

    assert ranks[first] == 1
    assert ranks[second] == 1
    assert ranks[third] == 2


def test_generate_request_requires_exactly_one_target():
    with pytest.raises(ValueError, match="Either student_id or class_id"):
        ReportCardGenerateRequest(
            academic_session_id=uuid4(),
            academic_term_id=uuid4(),
        )

    with pytest.raises(ValueError, match="either student_id or class_id"):
        ReportCardGenerateRequest(
            student_id=uuid4(),
            class_id=uuid4(),
            academic_session_id=uuid4(),
            academic_term_id=uuid4(),
        )


def test_class_generation_cannot_apply_one_principal_comment_to_every_student():
    base = {
        "class_id": uuid4(),
        "academic_session_id": uuid4(),
        "academic_term_id": uuid4(),
    }
    with pytest.raises(ValueError, match="grade defaults"):
        ReportCardGenerateRequest(
            **base,
            principal_comment="The same comment for everyone.",
        )
    with pytest.raises(ValueError, match="grade defaults"):
        ReportCardGenerateRequest(
            **base,
            principal_template_id=uuid4(),
        )

    payload = ReportCardGenerateRequest(
        **base,
        apply_default_principal_template=True,
    )
    assert payload.apply_default_principal_template is True


@pytest.mark.asyncio
async def test_generation_does_not_replace_current_authoritative_published_report(monkeypatch):
    tenant_id = uuid4()
    student_id = uuid4()
    actor = SimpleNamespace(id=uuid4(), tenant_id=tenant_id)
    student = SimpleNamespace(id=student_id)
    published = SimpleNamespace(id=uuid4(), is_outdated=False)

    monkeypatch.setattr(
        StudentRepository,
        "get_student_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "get_current_draft",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "get_current_published",
        AsyncMock(return_value=published),
    )

    with pytest.raises(BadRequestException, match="still authoritative"):
        await ReportCardService.generate_for_student(
            SimpleNamespace(),
            actor,
            student_id=student_id,
            academic_session_id=uuid4(),
            academic_term_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_archived_report_version_cannot_be_regenerated(monkeypatch):
    actor = SimpleNamespace(id=uuid4(), tenant_id=uuid4())
    archived = SimpleNamespace(
        id=uuid4(),
        status=ReportCardStatus.ARCHIVED,
        superseded_at=None,
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "get_by_id",
        AsyncMock(return_value=archived),
    )

    with pytest.raises(BadRequestException, match="Archived report cards cannot be regenerated"):
        await ReportCardService.regenerate(
            SimpleNamespace(), actor, archived.id
        )


@pytest.mark.asyncio
async def test_outdated_draft_cannot_be_published(monkeypatch):
    actor = SimpleNamespace(id=uuid4(), tenant_id=uuid4())
    draft = SimpleNamespace(
        id=uuid4(),
        status=ReportCardStatus.DRAFT,
        superseded_at=None,
        is_outdated=True,
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "get_by_id",
        AsyncMock(return_value=draft),
    )

    with pytest.raises(BadRequestException, match="must be regenerated"):
        await ReportCardService.publish(SimpleNamespace(), actor, draft.id)
