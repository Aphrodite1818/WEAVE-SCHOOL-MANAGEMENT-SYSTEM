import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_superadmin
from app.core.utils.frontend_urls import resolve_frontend_app_url
from app.modules.superadmin.models import PlatformControl, SecurityIPBlock, SuperAdmin
from app.modules.superadmin.platform_control_service import PlatformControlService
from app.modules.superadmin.schemas import (
    PlatformControlResponse,
    PlatformLockdownRequest,
    PlatformUnlockRequest,
    SecurityActionResponse,
    SecurityIPBlockCreate,
    SecurityIPBlockResponse,
    SecurityIPBlockUnblock,
    SecurityRevokeActorSessionsRequest,
    SecurityRevokeIPSessionsRequest,
    SuperadminInviteCreate,
    SuperadminResponse,
)
from app.modules.superadmin.security_response_service import SecurityResponseService
from app.modules.superadmin.security_service import SuperadminSecurityService
from app.modules.superadmin.service import SuperadminService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.tenant_management.models import Tenant
from app.tenant_management.schemas import (
    TenantManagementResponse,
    TenantCreate,
    TenantStatusUpdate,
)

router = APIRouter(prefix="/superadmin", tags=["Superadmin"])
SuperadminActor: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]


@router.post(
    "/tenants",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_201_CREATED,
)
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


@router.get(
    "/tenants",
    response_model=list[TenantManagementResponse],
    status_code=status.HTTP_200_OK,
)
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


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
    include_deleted: bool = Query(default=True),
) -> Tenant:
    """Return tenant."""
    return await SuperadminService.get_tenant(
        db, tenant_id, include_deleted=include_deleted
    )


@router.get("/tenants/{tenant_id}/usage", status_code=status.HTTP_200_OK)
async def get_tenant_usage(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, object]:
    """Return subscription entitlements and resource usage for one tenant."""

    tenant = await SuperadminService.get_tenant(db, tenant_id, include_deleted=True)
    entitlements = await SubscriptionFeatureService.get_tenant_entitlements(
        db=db,
        tenant_id=tenant.id,
        use_cache=False,
    )
    subscription = await SubscriptionFeatureService.get_current_subscription(
        db=db,
        tenant_id=tenant.id,
    )

    return {
        "tenant": TenantManagementResponse.model_validate(tenant).model_dump(
            mode="json"
        ),
        "entitlements": entitlements.model_dump(mode="json"),
        "subscription": subscription.model_dump(mode="json") if subscription else None,
    }


@router.patch(
    "/tenants/{tenant_id}/status",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_200_OK,
)
async def update_tenant_status(
    tenant_id: uuid.UUID,
    payload: TenantStatusUpdate,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> Tenant:
    """Update tenant status."""
    return await SuperadminService.update_tenant_status(db, tenant_id, payload)


@router.patch(
    "/tenants/{tenant_id}/restore",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_200_OK,
)
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


@router.get(
    "/superadmins",
    response_model=list[SuperadminResponse],
    status_code=status.HTTP_200_OK,
)
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


@router.get(
    "/security/ip-blocks",
    response_model=list[SecurityIPBlockResponse],
    status_code=status.HTTP_200_OK,
)
async def list_security_ip_blocks(
    db: DbSession,
    current_superadmin: SuperadminActor,
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SecurityIPBlock]:
    """List manual IP containment rules."""

    return await SecurityResponseService.list_ip_blocks(
        db,
        include_inactive=include_inactive,
        limit=limit,
    )


@router.post(
    "/security/ip-blocks",
    response_model=SecurityIPBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_security_ip_block(
    payload: SecurityIPBlockCreate,
    db: DbSession,
    background_tasks: BackgroundTasks,
    current_superadmin: SuperadminActor,
) -> SecurityIPBlock:
    """Create a manual IP containment rule."""

    return await SecurityResponseService.block_ip(
        db,
        background_tasks=background_tasks,
        current_superadmin=current_superadmin,
        payload=payload,
    )


@router.post(
    "/security/ip-blocks/{block_id}/unblock",
    response_model=SecurityIPBlockResponse,
    status_code=status.HTTP_200_OK,
)
async def unblock_security_ip(
    block_id: uuid.UUID,
    payload: SecurityIPBlockUnblock,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> SecurityIPBlock:
    """Disable a manual IP containment rule."""

    return await SecurityResponseService.unblock_ip(
        db,
        block_id=block_id,
        current_superadmin=current_superadmin,
        payload=payload,
    )


@router.post(
    "/security/revoke-ip-sessions",
    response_model=SecurityActionResponse,
    status_code=status.HTTP_200_OK,
)
async def revoke_ip_sessions(
    payload: SecurityRevokeIPSessionsRequest,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, int | str]:
    """Revoke active non-superadmin sessions from one IP address."""

    affected_count = await SecurityResponseService.revoke_sessions_for_ip(
        db,
        current_superadmin=current_superadmin,
        payload=payload,
    )
    return {"detail": "IP sessions revoked.", "affected_count": affected_count}


@router.post(
    "/security/revoke-actor-sessions",
    response_model=SecurityActionResponse,
    status_code=status.HTTP_200_OK,
)
async def revoke_actor_sessions(
    payload: SecurityRevokeActorSessionsRequest,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, int | str]:
    """Revoke active sessions for one actor."""

    affected_count = await SecurityResponseService.revoke_sessions_for_actor(
        db,
        current_superadmin=current_superadmin,
        payload=payload,
    )
    return {"detail": "Actor sessions revoked.", "affected_count": affected_count}


@router.get(
    "/platform-control",
    response_model=PlatformControlResponse,
    status_code=status.HTTP_200_OK,
)
async def get_platform_control(
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> dict[str, object]:
    """Return the current emergency platform-control state."""

    return await PlatformControlService.get_response(db)


@router.post(
    "/platform-control/lockdown",
    response_model=PlatformControlResponse,
    status_code=status.HTTP_200_OK,
)
async def enable_platform_lockdown(
    payload: PlatformLockdownRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
    current_superadmin: SuperadminActor,
) -> PlatformControl:
    """Enable emergency platform lockdown for non-superadmin traffic."""

    return await PlatformControlService.enable_lockdown(
        db,
        background_tasks=background_tasks,
        current_superadmin=current_superadmin,
        payload=payload,
    )


@router.post(
    "/platform-control/unlock",
    response_model=PlatformControlResponse,
    status_code=status.HTTP_200_OK,
)
async def disable_platform_lockdown(
    payload: PlatformUnlockRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
    current_superadmin: SuperadminActor,
) -> PlatformControl:
    """Disable emergency platform lockdown."""

    return await PlatformControlService.disable_lockdown(
        db,
        background_tasks=background_tasks,
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
