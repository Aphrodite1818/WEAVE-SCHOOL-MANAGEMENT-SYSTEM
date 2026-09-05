"""Shared validation for grade-scoped personal principal comments."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_models import (
    CommentTemplateOwnerType,
    CommentTemplateStatus,
)
from app.modules.report_cards.comment_schemas import CommentTemplateResponse
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.tenant_admins.models import TenantAdmin


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value))


async def require_admin_template_for_grade(
    db: AsyncSession,
    *,
    admin: TenantAdmin,
    template_id: UUID,
    grading_scale_id: UUID,
) -> CommentTemplateResponse:
    """Require one active personal admin comment mapped to exactly one expected grade."""

    templates = await ReportCommentService.list_templates(
        db,
        tenant_id=admin.tenant_id,
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=admin.id,
        include_archived=False,
    )
    template = next((item for item in templates if item.id == template_id), None)
    if template is None or _status_value(template.status) != CommentTemplateStatus.ACTIVE.value:
        raise BadRequestException("Principal comment is unavailable.")
    grade_ids = list(template.grading_scale_ids or [])
    if len(grade_ids) != 1 or grade_ids[0] != grading_scale_id:
        raise BadRequestException(
            "The selected principal comment is not assigned to this student's calculated grade."
        )
    return template
