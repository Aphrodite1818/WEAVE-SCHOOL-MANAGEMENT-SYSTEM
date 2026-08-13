# ==========================#
# cbt/pairing/router.py
# ==========================#


"""HTTP routes for pairing local CBT servers with Weave tenants"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.cbt.pairing.schemas import (
    CBTServerCredentialRotationResponse,
    CBTServerListResponse,
    CBTServerResponse,
    CBTServerRevokeRequest,
    PairingCode,
    PairingRequest,
    PairingResult,
)
from app.modules.cbt.pairing.service import CBTPairingService
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(tags=["CBT Pairing"])


CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post("/pairing/codes", response_model=PairingCode, status_code=status.HTTP_201_CREATED)
async def create_pairing_code(db: DbSession, current_admin: CurrentTenantAdmin) -> PairingCode:
    """
    Generate a short-lived pairing code for the authenticated tenant

    Only an authenticated tenant administrator may generate a pairing
    code. Tenant and administrator identity are derived from the current
    authenticated session and are never accepted from the request body
    """

    return await CBTPairingService.create_pairing_code(
        db=db,
        admin=current_admin,
    )


@router.post("/pairing/verify", response_model=PairingResult, status_code=status.HTTP_201_CREATED)
async def pair_server(db: DbSession, payload: PairingRequest) -> PairingResult:
    """
    Exchange a valid one-time pairing code for CBT server credentials

    This endpoint intentionally does not require a normal Weave user
    session. The short-lived pairing code acts as a bootstrap
    authorization for the local CBT server

    Tenant ownership is determined exclusively from the stored pairing code
    """

    return await CBTPairingService.pair_server(
        db=db,
        payload=payload,
    )


@router.get(
    "/servers",
    response_model=CBTServerListResponse,
)
async def list_cbt_servers(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerListResponse:
    return await CBTPairingService.list_servers(
        db=db,
        admin=current_admin,
    )


@router.get(
    "/servers/{server_id}",
    response_model=CBTServerResponse,
)
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


@router.post(
    "/servers/{server_id}/suspend",
    response_model=CBTServerResponse,
)
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


@router.post(
    "/servers/{server_id}/reactivate",
    response_model=CBTServerResponse,
)
async def reactivate_cbt_server(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    return await CBTPairingService.reactivate_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )


@router.post(
    "/servers/{server_id}/revoke",
    response_model=CBTServerResponse,
)
async def revoke_cbt_server(
    server_id: UUID,
    payload: CBTServerRevokeRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerResponse:
    return await CBTPairingService.revoke_server(
        db=db,
        admin=current_admin,
        server_id=server_id,
        reason=payload.reason,
        confirmation_literal=payload.confirmation_literal,
    )


@router.post(
    "/servers/{server_id}/rotate-credential",
    response_model=CBTServerCredentialRotationResponse,
)
async def rotate_cbt_server_credential(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerCredentialRotationResponse:
    return await CBTPairingService.rotate_server_credential(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )
