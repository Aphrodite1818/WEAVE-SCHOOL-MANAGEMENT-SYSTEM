from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.report_cards.generation_service import EnrollmentReportCardService
from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardClassOverviewResponse,
    ReportCardGenerateRequest,
    ReportCardResponse,
)
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/tenant-admin/academic/report-cards",
    tags=["Tenant Admin Report Cards"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
)
async def generate_report_card(
    payload: ReportCardGenerateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ReportCardResponse | ReportCardBulkGenerateResponse:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_admin.tenant_id,
        feature=FeatureCode.REPORT_CARDS,
    )
    return await EnrollmentReportCardService.generate(db, current_admin, payload)


@router.get("/overview", response_model=ReportCardClassOverviewResponse)
async def report_card_class_overview(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    class_id: UUID = Query(...),
    academic_session_id: UUID = Query(...),
    academic_term_id: UUID = Query(...),
) -> ReportCardClassOverviewResponse:
    return await EnrollmentReportCardService.class_overview(
        db,
        current_admin,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )
