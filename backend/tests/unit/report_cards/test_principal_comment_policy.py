from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_models import CommentTemplateOwnerType
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.principal_comment_policy import (
    require_admin_template_for_performance,
)
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
async def test_principal_template_must_cover_calculated_performance(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    selected_id = uuid4()
    monkeypatch.setattr(
        ReportCommentService,
        "templates_for_performance",
        AsyncMock(return_value=[SimpleNamespace(id=uuid4())]),
    )

    with pytest.raises(BadRequestException, match="performance range"):
        await require_admin_template_for_performance(
            SimpleNamespace(),
            admin=admin,
            template_id=selected_id,
            performance_percentage=Decimal("68.25"),
        )


@pytest.mark.asyncio
async def test_principal_template_accepts_owned_range_match(monkeypatch) -> None:
    admin = TenantAdmin(tenant_id=uuid4())
    admin.id = uuid4()
    template = SimpleNamespace(id=uuid4(), minimum_score=Decimal("60"), maximum_score=Decimal("70"))
    lookup = AsyncMock(return_value=[template])
    monkeypatch.setattr(ReportCommentService, "templates_for_performance", lookup)

    result = await require_admin_template_for_performance(
        SimpleNamespace(),
        admin=admin,
        template_id=template.id,
        performance_percentage=Decimal("70"),
    )

    assert result is template
    lookup.assert_awaited_once_with(
        ANY,
        tenant_id=admin.tenant_id,
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=admin.id,
        performance_percentage=Decimal("70"),
    )
