"""Tenant-admin routes for opening sessions and running progression."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.lifecycle_schemas import (
    AcademicSessionCloseRequest,
    AcademicSessionOpenRequest,
)
from app.modules.student_academics.lifecycle_service import (
    AcademicSessionLifecycleService,
)
from app.modules.student_academics.schemas import (
    AcademicSessionCloseResponse,
    AcademicSessionResponse,
    StudentProgressionRunDetailResponse,
)
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academic/session-lifecycle",
    tags=["Tenant Admin Academic Lifecycle"],
)
CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


@router.post(
    "/sessions/{session_id}/open",
    response_model=AcademicSessionResponse,
)
async def open_academic_session(
    session_id: UUID,
    payload: AcademicSessionOpenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_admin.tenant_id,
        feature=FeatureCode.ACADEMIC_SETUP,
    )
    return await AcademicSessionLifecycleService.open_session(
        db,
        actor=current_admin,
        session_id=session_id,
        payload=payload,
    )


@router.post(
    "/sessions/{session_id}/close",
    response_model=AcademicSessionCloseResponse,
)
async def close_academic_session(
    session_id: UUID,
    payload: AcademicSessionCloseRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionCloseResponse:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_admin.tenant_id,
        feature=FeatureCode.ACADEMIC_SETUP,
    )
    return await AcademicSessionLifecycleService.close_session(
        db,
        actor=current_admin,
        session_id=session_id,
        payload=payload,
    )


@router.get(
    "/progression-runs/{run_id}",
    response_model=StudentProgressionRunDetailResponse,
)
async def get_progression_run(
    run_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentProgressionRunDetailResponse:
    return await AcademicSessionLifecycleService.get_progression_run(
        db,
        actor=current_admin,
        run_id=run_id,
    )
