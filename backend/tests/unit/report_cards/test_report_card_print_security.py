import inspect
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.report_cards import router
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.print_service import ReportCardPrintService
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.schemas import ReportCardPrincipalCommentUpdate
from app.modules.report_cards.service import ReportCardService
from app.tenant_management.repository import TenantRepository


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


def test_canonical_report_card_template_is_print_safe():
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
async def test_published_report_card_principal_comment_is_immutable(monkeypatch):
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

    with pytest.raises(BadRequestException, match="Published report revisions are immutable"):
        await ReportCardService.update_principal_comment(
            SimpleNamespace(),
            actor,
            card.id,
            ReportCardPrincipalCommentUpdate(principal_comment="Updated principal comment"),
        )


@pytest.mark.asyncio
async def test_print_uses_stored_report_snapshot_instead_of_live_class_configuration(monkeypatch):
    tenant_id = uuid4()
    card_id = uuid4()
    now = datetime.now(timezone.utc)
    actor = SimpleNamespace(id=uuid4(), tenant_id=tenant_id)
    snapshot = SimpleNamespace(
        id=card_id,
        tenant_id=tenant_id,
        student_name="Ada Student",
        admission_number="STD-001",
        student_passport_photo_url=None,
        class_name="SS1",
        class_arm="C",
        department_name="Science",
        class_teacher_name="Snapshot Teacher",
        academic_session_name="2026/2027",
        academic_term_name="FIRST",
        total_score=Decimal("180"),
        average_score=Decimal("90"),
        position=1,
        position_out_of=30,
        class_teacher_comment="Excellent consistency.",
        principal_comment="Outstanding performance.",
        version=2,
        status=ReportCardStatus.PUBLISHED,
        published_at=now,
        lines=[],
    )
    tenant = SimpleNamespace(
        school_name="Snapshot School",
        address="Lagos",
        phone="08000000000",
        email="school@example.com",
        logo_url=None,
    )

    monkeypatch.setattr(
        ReportCardService,
        "get",
        AsyncMock(return_value=snapshot),
    )
    monkeypatch.setattr(
        TenantRepository,
        "get_by_id",
        AsyncMock(return_value=tenant),
    )

    html = await ReportCardPrintService.render_html(
        SimpleNamespace(), actor, card_id
    )

    assert "SS1 C" in html
    assert "Excellent consistency." in html
    assert "Outstanding performance." in html
    assert "2026/2027" in html
    ReportCardService.get.assert_awaited_once_with(
        pytest.ANY if hasattr(pytest, "ANY") else SimpleNamespace(), actor, card_id
    )
