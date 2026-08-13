"""Tenant-admin CBT pairing and server lifecycle routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import ForbiddenException
from app.modules.cbt.pairing.schemas import (
    CBTServerListResponse,
    CBTServerResponse,
    CBTServerRevokeRequest,
    PairingCode,
)
from app.modules.cbt.pairing.service import CBTPairingService
from app.modules.cbt.pairing.status_schemas import PairingStatusRequest, PairingStatusResponse
from app.modules.cbt.pairing.status_service import CBTPairingStatusService
from app.modules.cbt.repository import CBTServerRepository
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(tags=["CBT Pairing"])
CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


def tenant_id_for(admin: TenantAdmin) -> UUID:
    if admin.tenant_id is None:
        raise ForbiddenException(detail="Tenant admin is not attached to a tenant")
    return admin.tenant_id


@router.post("/pairing/codes", response_model=PairingCode, status_code=status.HTTP_201_CREATED)
async def create_pairing_code(db: DbSession, current_admin: CurrentTenantAdmin) -> PairingCode:
    return await CBTPairingService.create_pairing_code(db=db, admin=current_admin)


@router.post("/pairing/status", response_model=PairingStatusResponse)
async def get_pairing_status(
    payload: PairingStatusRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> PairingStatusResponse:
    return await CBTPairingStatusService.get_status(
        db,
        admin=current_admin,
        pairing_code=payload.pairing_code,
    )


@router.get("/servers", response_model=CBTServerListResponse)
async def list_cbt_servers(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerListResponse:
    servers = await CBTServerRepository.list_for_tenant(db, tenant_id_for(current_admin))
    items = [CBTServerResponse.model_validate(server) for server in servers]
    return CBTServerListResponse(items=items, total=len(items))


@router.get("/servers/{server_id}", response_model=CBTServerResponse)
async def get_cbt_server(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    return await CBTPairingService.get_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )


@router.post("/servers/{server_id}/suspend", response_model=CBTServerResponse)
async def suspend_cbt_server(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    return await CBTPairingService.suspend_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )


@router.post("/servers/{server_id}/reactivate", response_model=CBTServerResponse)
async def reactivate_cbt_server(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    tenant_id = tenant_id_for(current_admin)
    await SubscriptionFeatureService.ensure_feature_enabled(
        db,
        tenant_id,
        FeatureCode.CBT_PAIRING,
    )
    return await CBTPairingService.reactivate_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )


@router.post("/servers/{server_id}/revoke", response_model=CBTServerResponse)
async def revoke_cbt_server(
    server_id: UUID,
    payload: CBTServerRevokeRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    result = await CBTPairingService.revoke_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
        reason=payload.reason,
        confirmation_literal=payload.confirmation_literal,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(
        tenant_id_for(current_admin),
        db=db,
    )
    return result
