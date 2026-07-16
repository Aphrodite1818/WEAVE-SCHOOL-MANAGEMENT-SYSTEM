"""Tenant-admin academic session opening, closure, and progression routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.student_academics.schemas import (
    AcademicSessionCloseRequest,
    AcademicSessionCloseResponse,
    AcademicSessionOpenRequest,
    AcademicSessionResponse,
)
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/sessions",
    tags=["Tenant Admin Academics"],
)
CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


@router.post(
    "/{session_id}/open",
    response_model=AcademicSessionResponse,
)
async def open_academic_session(
    session_id: UUID,
    payload: AcademicSessionOpenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    _ = payload.confirmation
    return await AcademicProgressionService.open_session(
        db,
        actor=current_admin,
        session_id=session_id,
    )


@router.post(
    "/{session_id}/close-and-progress",
    response_model=AcademicSessionCloseResponse,
)
async def close_academic_session_and_progress(
    session_id: UUID,
    payload: AcademicSessionCloseRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionCloseResponse:
    _ = payload.confirmation
    return await AcademicProgressionService.close_and_progress(
        db,
        actor=current_admin,
        session_id=session_id,
        idempotency_key=payload.idempotency_key,
    )
