"""Validation for performance-range principal comment selection."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_models import CommentTemplateOwnerType
from app.modules.report_cards.comment_schemas import CommentTemplateResponse
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.tenant_admins.models import TenantAdmin


async def require_admin_template_for_performance(
    db: AsyncSession,
    *,
    admin: TenantAdmin,
    template_id: UUID,
    performance_percentage: Decimal,
) -> CommentTemplateResponse:
    """Require an active admin comment covering the calculated performance."""

    matches = await ReportCommentService.templates_for_performance(
        db,
        tenant_id=admin.tenant_id,
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=admin.id,
        performance_percentage=performance_percentage,
    )
    template = next((item for item in matches if item.id == template_id), None)
    if template is None:
        raise BadRequestException(
            "The selected principal comment does not match this student's overall performance range."
        )
    return template
