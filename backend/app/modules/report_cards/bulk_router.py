from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.report_cards.bulk_schemas import (
    BulkActionResponse,
    ReportCardBulkArchiveRequest,
    ReportCardBulkPublishRequest,
    ReportCardBulkReopenRequest,
)
from app.modules.report_cards.bulk_service import BulkReportCardService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/tenant-admin/academic/report-cards/bulk",
    tags=["Tenant Admin Report Card Bulk Actions"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


async def _ensure_paid_bulk_academics(
    db: DbSession,
    actor: TenantAdmin,
) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=actor.tenant_id,
        feature=FeatureCode.BULK_ACADEMIC_OPERATIONS,
    )


@router.post("/publish", response_model=BulkActionResponse)
async def bulk_publish_report_cards(
    payload: ReportCardBulkPublishRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> BulkActionResponse:
    await _ensure_paid_bulk_academics(db, current_admin)
    return await BulkReportCardService.publish(db, current_admin, payload)


@router.post("/archive", response_model=BulkActionResponse)
async def bulk_archive_report_cards(
    payload: ReportCardBulkArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> BulkActionResponse:
    await _ensure_paid_bulk_academics(db, current_admin)
    return await BulkReportCardService.archive(db, current_admin, payload)


@router.post("/reopen", response_model=BulkActionResponse)
async def bulk_reopen_report_cards(
    payload: ReportCardBulkReopenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> BulkActionResponse:
    await _ensure_paid_bulk_academics(db, current_admin)
    return await BulkReportCardService.reopen(db, current_admin, payload)
