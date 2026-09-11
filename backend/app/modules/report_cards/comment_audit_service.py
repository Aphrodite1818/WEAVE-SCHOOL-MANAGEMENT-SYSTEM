from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.report_cards.comment_models import TeacherCommentOverride
from app.modules.report_cards.comment_schemas import TeacherCommentOverrideResponse
from app.modules.tenant_admins.models import TenantAdmin


class TeacherCommentAuditService:
    """Read-only audit access for append-only teacher-comment overrides."""

    @staticmethod
    async def list_overrides(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[TeacherCommentOverrideResponse]:
        items = list(
            (
                await db.execute(
                    select(TeacherCommentOverride)
                    .where(
                        TeacherCommentOverride.tenant_id == admin.tenant_id,
                        TeacherCommentOverride.student_id == student_id,
                        TeacherCommentOverride.academic_session_id == academic_session_id,
                        TeacherCommentOverride.academic_term_id == academic_term_id,
                    )
                    .order_by(
                        TeacherCommentOverride.created_at.desc(),
                        TeacherCommentOverride.id.desc(),
                    )
                )
            ).scalars()
        )
        return [TeacherCommentOverrideResponse.model_validate(item) for item in items]
