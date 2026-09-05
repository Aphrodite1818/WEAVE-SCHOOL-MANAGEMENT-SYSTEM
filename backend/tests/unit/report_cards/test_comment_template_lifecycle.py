from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.report_cards.comment_models import CommentTemplateStatus
from app.modules.report_cards.comment_router import (
    _delete_personal_comment,
    _update_personal_comment,
)
from app.modules.report_cards.comment_schemas import PersonalCommentTemplateUpdate
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.tenant_admins.models import TenantAdmin


def _template(*, template_id, grade_id, is_default, status=CommentTemplateStatus.ACTIVE):
    return SimpleNamespace(
        id=template_id,
        text="Saved comment",
        status=status,
        grading_scale_ids=[grade_id],
        default_grading_scale_ids=[grade_id] if is_default else [],
    )


@pytest.mark.asyncio
async def test_cannot_deactivate_default_while_other_active_comment_has_no_default(monkeypatch) -> None:
    grade_id = uuid4()
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    current = _template(template_id=uuid4(), grade_id=grade_id, is_default=True)
    alternative = _template(template_id=uuid4(), grade_id=grade_id, is_default=False)

    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._find_template",
        AsyncMock(return_value=current),
    )
    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._owned_templates",
        AsyncMock(return_value=[current, alternative]),
    )

    with pytest.raises(ConflictException, match="another active comment as the default"):
        await _update_personal_comment(
            SimpleNamespace(),
            admin,
            current.id,
            PersonalCommentTemplateUpdate(status=CommentTemplateStatus.INACTIVE),
        )


@pytest.mark.asyncio
async def test_cannot_delete_default_while_other_active_comment_exists(monkeypatch) -> None:
    grade_id = uuid4()
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    current = _template(template_id=uuid4(), grade_id=grade_id, is_default=True)
    alternative = _template(template_id=uuid4(), grade_id=grade_id, is_default=False)
    delete_template = AsyncMock()

    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._find_template",
        AsyncMock(return_value=current),
    )
    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._owned_templates",
        AsyncMock(return_value=[current, alternative]),
    )
    monkeypatch.setattr(ReportCommentService, "delete_template", delete_template)

    with pytest.raises(ConflictException, match="another active comment as the default"):
        await _delete_personal_comment(SimpleNamespace(), admin, current.id)

    delete_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_active_comment_for_grade_can_be_deleted_if_unused(monkeypatch) -> None:
    grade_id = uuid4()
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    current = _template(template_id=uuid4(), grade_id=grade_id, is_default=True)
    delete_template = AsyncMock()

    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._find_template",
        AsyncMock(return_value=current),
    )
    monkeypatch.setattr(
        "app.modules.report_cards.comment_router._owned_templates",
        AsyncMock(return_value=[current]),
    )
    monkeypatch.setattr(ReportCommentService, "delete_template", delete_template)

    await _delete_personal_comment(SimpleNamespace(), admin, current.id)

    delete_template.assert_awaited_once_with(
        ANY,
        actor=admin,
        template_id=current.id,
    )
