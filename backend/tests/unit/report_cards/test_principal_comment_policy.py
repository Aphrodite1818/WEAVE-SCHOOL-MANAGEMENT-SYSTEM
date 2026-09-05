from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_models import (
    CommentTemplateOwnerType,
    CommentTemplateStatus,
)
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.principal_comment_policy import require_admin_template_for_grade
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
async def test_principal_template_must_match_calculated_grade(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    template_id = uuid4()
    expected_grade_id = uuid4()
    wrong_grade_id = uuid4()
    monkeypatch.setattr(
        ReportCommentService,
        "list_templates",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=template_id,
                    status=CommentTemplateStatus.ACTIVE,
                    grading_scale_ids=[wrong_grade_id],
                )
            ]
        ),
    )

    with pytest.raises(BadRequestException, match="calculated grade"):
        await require_admin_template_for_grade(
            SimpleNamespace(),
            admin=admin,
            template_id=template_id,
            grading_scale_id=expected_grade_id,
        )


@pytest.mark.asyncio
async def test_principal_template_must_be_active_and_personally_owned(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    template_id = uuid4()
    list_templates = AsyncMock(return_value=[])
    monkeypatch.setattr(ReportCommentService, "list_templates", list_templates)

    with pytest.raises(BadRequestException, match="unavailable"):
        await require_admin_template_for_grade(
            SimpleNamespace(),
            admin=admin,
            template_id=template_id,
            grading_scale_id=uuid4(),
        )

    list_templates.assert_awaited_once_with(
        pytest.ANY,
        tenant_id=admin.tenant_id,
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=admin.id,
        include_archived=False,
    )


@pytest.mark.asyncio
async def test_principal_template_accepts_one_active_comment_for_exact_grade(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    template_id = uuid4()
    grade_id = uuid4()
    template = SimpleNamespace(
        id=template_id,
        status=CommentTemplateStatus.ACTIVE,
        grading_scale_ids=[grade_id],
    )
    monkeypatch.setattr(
        ReportCommentService,
        "list_templates",
        AsyncMock(return_value=[template]),
    )

    result = await require_admin_template_for_grade(
        SimpleNamespace(),
        admin=admin,
        template_id=template_id,
        grading_scale_id=grade_id,
    )

    assert result is template


@pytest.mark.asyncio
async def test_obsolete_multi_grade_principal_template_is_rejected(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    grade_id = uuid4()
    template = SimpleNamespace(
        id=uuid4(),
        status=CommentTemplateStatus.ACTIVE,
        grading_scale_ids=[grade_id, uuid4()],
    )
    monkeypatch.setattr(
        ReportCommentService,
        "list_templates",
        AsyncMock(return_value=[template]),
    )

    with pytest.raises(BadRequestException, match="calculated grade"):
        await require_admin_template_for_grade(
            SimpleNamespace(),
            admin=admin,
            template_id=template.id,
            grading_scale_id=grade_id,
        )
