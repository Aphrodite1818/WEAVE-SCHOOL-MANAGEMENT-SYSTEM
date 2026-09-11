from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import BadRequestException
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.principal_comment_policy import require_admin_template_for_grade
from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardClassOverviewResponse,
    ReportCardGenerateRequest,
    ReportCardResponse,
)
from app.modules.report_cards.service import ReportCardService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academic/report-cards",
    tags=["Tenant Admin Report Cards"],
)
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_report_card(
    payload: ReportCardGenerateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ReportCardResponse | ReportCardBulkGenerateResponse:
    feature = (
        FeatureCode.BULK_ACADEMIC_OPERATIONS
        if payload.class_id is not None
        else FeatureCode.REPORT_CARDS
    )
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_admin.tenant_id,
        feature=feature,
    )
    if payload.student_id is not None and payload.principal_template_id is not None:
        ready, _, grading_scale = await ReportCommentService._academic_readiness(
            db,
            tenant_id=current_admin.tenant_id,
            student_id=payload.student_id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
        )
        if not ready or grading_scale is None:
            raise BadRequestException(
                "Principal comments can be selected after the student's final grade is resolved."
            )
        await require_admin_template_for_grade(
            db,
            admin=current_admin,
            template_id=payload.principal_template_id,
            grading_scale_id=grading_scale.id,
        )
    return await ReportCardService.generate(db, current_admin, payload)


@router.get("/overview", response_model=ReportCardClassOverviewResponse)
async def report_card_class_overview(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    class_id: UUID = Query(...),
    academic_session_id: UUID = Query(...),
    academic_term_id: UUID = Query(...),
) -> ReportCardClassOverviewResponse:
    return await ReportCardService.class_overview(
        db,
        current_admin,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )
