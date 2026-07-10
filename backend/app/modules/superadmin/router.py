import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import require_superadmin
from app.core.utils.frontend_urls import resolve_frontend_app_url
from app.modules.superadmin.models import PlatformControl, SuperAdmin
from app.modules.superadmin.platform_control_service import PlatformControlService
from app.modules.superadmin.schemas import (
    PlatformControlResponse,
    PlatformLockdownRequest,
    PlatformUnlockRequest,
    SuperadminInviteCreate,
    SuperadminResponse,
)
from app.modules.superadmin.security_service import SuperadminSecurityService
from app.modules.superadmin.service import SuperadminService
from app.tenant_management.models import Tenant
from app.tenant_management.schemas import TenantManagementResponse, TenantCreate, TenantStatusUpdate


router = APIRouter(prefix="/superadmin", tags=["Superadmin"])
SuperadminActor: TypeAlias = Annotated[SuperAdmin, Depends(require_superadmin)]


@router.post("/tenants", response_model=TenantManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    db: DbSession,
    background_tasks: BackgroundTasks,
    request: Request,
    current_superadmin: SuperadminActor,
) -> Tenant:
    """Create tenant."""
    return await SuperadminService.create_tenant(
        db,
        payload,
        background_tasks=background_tasks,
        frontend_app_url=resolve_frontend_app_url(request),
    )


@router.get("/tenants", response_model=list[TenantManagementResponse], status_code=status.HTTP_200_OK)
async def list_tenants(
    db: DbSession,
    current_superadmin: SuperadminActor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_deleted: bool = Query(default=True),
) -> list[Tenant]:
    """List tenants."""
    return await SuperadminService.list_tenants(
        db,
        skip=skip,
        limit=limit,
        include_deleted=include_deleted,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantManagementResponse, status_code=status.HTTP_200_OK)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
    include_deleted: bool = Query(default=True),
) -> Tenant:
    """Return tenant."""
    return await SuperadminService.get_tenant(db, tenant_id, include_deleted=include_deleted)


@router.patch("/tenants/{tenant_id}/status", response_model=TenantManagementResponse, status_code=status.HTTP_200_OK)
async def update_tenant_status(
    tenant_id: uuid.UUID,
    payload: TenantStatusUpdate,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> Tenant:
    """Update tenant status."""
    return await SuperadminService.update_tenant_status(db, tenant_id, payload)


@router.patch("/tenants/{tenant_id}/restore", response_model=TenantManagementResponse, status_code=status.HTTP_200_OK)
async def restore_tenant(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> Tenant:
    """Perform restore tenant."""
    return await SuperadminService.restore_tenant(db, tenant_id)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
async def delete_tenant(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, str]:
    """Delete tenant."""
    return await SuperadminService.delete_tenant(db, tenant_id)


@router.get("/superadmins", response_model=list[SuperadminResponse], status_code=status.HTTP_200_OK)
async def list_superadmins(
    db: DbSession,
    current_superadmin: SuperadminActor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SuperAdmin]:
    """List superadmins."""
    return await SuperadminService.list_superadmins(db, skip=skip, limit=limit)


@router.get("/analytics/overview", status_code=status.HTTP_200_OK)
async def get_superadmin_analytics_overview(
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, object]:
    """Return analytics data for the superadmin dashboard."""

    return await SuperadminService.get_analytics_overview(db)


@router.get("/security/overview", status_code=status.HTTP_200_OK)
async def get_superadmin_security_overview(
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, object]:
    """Return security signals for the superadmin dashboard."""

    return await SuperadminSecurityService.get_overview(db)


@router.get("/platform-control", response_model=PlatformControlResponse, status_code=status.HTTP_200_OK)
async def get_platform_control(
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, object]:
    """Return the current emergency platform-control state."""

    return await PlatformControlService.get_response(db)


@router.post("/platform-control/lockdown", response_model=PlatformControlResponse, status_code=status.HTTP_200_OK)
async def enable_platform_lockdown(
    payload: PlatformLockdownRequest,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> PlatformControl:
    """Enable emergency platform lockdown for non-superadmin traffic."""

    return await PlatformControlService.enable_lockdown(
        db,
        current_superadmin=current_superadmin,
        payload=payload,
    )


@router.post("/platform-control/unlock", response_model=PlatformControlResponse, status_code=status.HTTP_200_OK)
async def disable_platform_lockdown(
    payload: PlatformUnlockRequest,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> PlatformControl:
    """Disable emergency platform lockdown."""

    return await PlatformControlService.disable_lockdown(
        db,
        current_superadmin=current_superadmin,
        payload=payload,
    )


@router.post("/superadmins/invite", status_code=status.HTTP_201_CREATED)
async def invite_superadmin(
    payload: SuperadminInviteCreate,
    db: DbSession,
    background_tasks: BackgroundTasks,
    request: Request,
    current_superadmin: SuperadminActor,
) -> dict[str, str]:
    """Perform invite superadmin."""
    return await SuperadminService.invite_superadmin(
        db,
        invited_by=current_superadmin,
        payload=payload,
        background_tasks=background_tasks,
        frontend_app_url=resolve_frontend_app_url(request),
    )
