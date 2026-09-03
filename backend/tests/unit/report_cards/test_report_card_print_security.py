import inspect
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.report_cards import router
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.print_service import ReportCardPrintService
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.schemas import ReportCardCommentsUpdate
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.subjects.repository import SubjectRepository


def test_report_card_html_response_headers_prevent_sensitive_caching():
    headers = router.REPORT_CARD_HTML_HEADERS

    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in headers["Content-Security-Policy"]


def test_report_card_data_response_headers_prevent_sensitive_caching():
    headers = router.REPORT_CARD_DATA_HEADERS

    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"


def test_canonical_report_card_template_is_print_safe_and_omits_subject_teacher():
    source = inspect.getsource(ReportCardPrintService.render_html)

    assert "onclick=" not in source
    assert "document.write" not in source
    assert "dangerouslySetInnerHTML" not in source
    assert "<th>Teacher" not in source
    assert "Admission number" in source
    assert "Class teacher's comment" in source
    assert "Principal's comment" in source
    assert "weave-email-icon.png" in source


@pytest.mark.asyncio
async def test_published_report_card_comments_are_immutable(monkeypatch):
    card = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        status=ReportCardStatus.PUBLISHED,
        superseded_at=None,
    )
    actor = SimpleNamespace(id=uuid4(), tenant_id=card.tenant_id)
    monkeypatch.setattr(
        ReportCardRepository,
        "get_by_id",
        AsyncMock(return_value=card),
    )

    with pytest.raises(
        BadRequestException,
        match="Only draft report cards can be edited",
    ):
        await ReportCardService.update_comments(
            SimpleNamespace(),
            actor,
            card.id,
            ReportCardCommentsUpdate(class_teacher_comment="Updated"),
        )


@pytest.mark.asyncio
async def test_regeneration_archives_outdates_old_card_and_creates_next_draft_version(
    monkeypatch,
):
    tenant_id = uuid4()
    subject_id = uuid4()
    existing = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        student_id=uuid4(),
        class_id=uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        class_teacher_comment="Steady progress",
        principal_comment="Keep improving",
        version=2,
        status=ReportCardStatus.PUBLISHED,
        is_outdated=False,
        superseded_at=None,
    )
    actor = SimpleNamespace(id=uuid4(), tenant_id=tenant_id)
    student = SimpleNamespace(id=existing.student_id, class_id=existing.class_id)
    result = SimpleNamespace(
        id=uuid4(),
        status=AcademicResultStatus.LOCKED,
        subject_id=subject_id,
        curriculum_subject_id=uuid4(),
        teacher_assignment_id=None,
        teacher_membership_id=uuid4(),
        total_score=Decimal("90"),
        grade="A",
        remark="Excellent",
    )

    async def _save(_db, entity):
        return entity

    async def _create(_db, card):
        card.id = uuid4()
        return card

    monkeypatch.setattr(
        ReportCardService,
        "_missing_subjects",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        ReportCardService,
        "_expected_curriculum_subjects",
        AsyncMock(return_value=[SimpleNamespace(curriculum_subject_id=result.curriculum_subject_id)]),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "save",
        AsyncMock(side_effect=_save),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "create",
        AsyncMock(side_effect=_create),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "create_line",
        AsyncMock(side_effect=_save),
    )
    monkeypatch.setattr(
        ReportCardRepository,
        "create_component",
        AsyncMock(side_effect=_save),
    )
    component = SimpleNamespace(
        id=uuid4(),
        name="Final",
        code="FINAL",
        position=0,
        maximum_score=Decimal("100"),
    )
    score = SimpleNamespace(score=Decimal("90"))
    monkeypatch.setattr(
        StudentAcademicRepository,
        "list_result_component_scores_batch",
        AsyncMock(return_value={result.id: [(component, score)]}),
    )
    monkeypatch.setattr(
        SubjectRepository,
        "get_subject_by_id",
        AsyncMock(return_value=SimpleNamespace(name="Mathematics", code="MTH")),
    )
    monkeypatch.setattr(
        ReportCardService,
        "_teacher_name_for_result",
        AsyncMock(return_value="Teacher Example"),
    )

    enrollment_result = MagicMock()
    enrollment_result.scalar_one_or_none.return_value = SimpleNamespace(class_id=existing.class_id)
    db = MagicMock()
    db.execute = AsyncMock(return_value=enrollment_result)

    new_card = await ReportCardService._create_card_from_results(
        db,
        actor,
        student,
        existing.academic_session_id,
        existing.academic_term_id,
        [result],
        replace_existing=existing,
    )

    assert existing.status == ReportCardStatus.ARCHIVED
    assert existing.is_outdated is True
    assert existing.superseded_at is not None
    assert new_card.version == 3
    assert new_card.status == ReportCardStatus.DRAFT
    assert new_card.published_at is None
    assert new_card.published_by is None
