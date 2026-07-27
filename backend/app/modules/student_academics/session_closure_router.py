"""Tenant-admin endpoints for staged academic-session closure."""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.schemas import AcademicSessionCloseRequest
from app.modules.student_academics.session_closure_schemas import (
    SessionClosureAuditResponse,
    SessionClosureFinalizeRequest,
    SessionClosureFinalizeResponse,
    SessionClosureStartRequest,
    SessionClosureStartResponse,
    SessionClosureStatusResponse,
    SessionProgressionRetryRequest,
)
from app.modules.student_academics.session_closure_service import SessionClosureService
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/tenant-admin/academics/sessions",
    tags=["Academic Session Closure"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


@router.get("/{session_id}/closure-audit", response_model=SessionClosureAuditResponse)
async def get_closure_audit(
    session_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureAuditResponse:
    return await SessionClosureService.audit(
        db,
        tenant_id=current_admin.tenant_id,
        session_id=session_id,
    )


@router.post("/{session_id}/start-closing", response_model=SessionClosureStartResponse)
async def start_session_closing(
    session_id: UUID,
    payload: SessionClosureStartRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureStartResponse:
    _ = payload.confirmation
    return await SessionClosureService.start_closing(
        db,
        actor=current_admin,
        session_id=session_id,
        idempotency_key=payload.idempotency_key,
    )


# Backward-compatible path. It no longer closes or opens sessions atomically;
# it only starts the staged CLOSING workflow.
@router.post("/{session_id}/close-and-progress", response_model=SessionClosureStartResponse)
async def legacy_close_and_progress_starts_closing(
    session_id: UUID,
    payload: AcademicSessionCloseRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureStartResponse:
    _ = payload.confirmation
    return await SessionClosureService.start_closing(
        db,
        actor=current_admin,
        session_id=session_id,
        idempotency_key=payload.idempotency_key,
    )


@router.get("/{session_id}/closing-status", response_model=SessionClosureStatusResponse)
async def get_session_closing_status(
    session_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureStatusResponse:
    return await SessionClosureService.status(
        db,
        tenant_id=current_admin.tenant_id,
        session_id=session_id,
    )


@router.post("/{session_id}/retry-progression", response_model=SessionClosureStatusResponse)
async def retry_session_progression(
    session_id: UUID,
    payload: SessionProgressionRetryRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureStatusResponse:
    _ = payload.confirmation
    return await SessionClosureService.retry(
        db,
        actor=current_admin,
        session_id=session_id,
    )


@router.post("/{session_id}/finalize-close", response_model=SessionClosureFinalizeResponse)
async def finalize_session_close(
    session_id: UUID,
    payload: SessionClosureFinalizeRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SessionClosureFinalizeResponse:
    _ = payload.confirmation
    return await SessionClosureService.finalize(
        db,
        actor=current_admin,
        session_id=session_id,
    )
