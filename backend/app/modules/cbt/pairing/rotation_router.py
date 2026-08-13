"""Tenant-admin CBT server key rotation route."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.cbt.pairing.admin_management_router import tenant_id_for
from app.modules.cbt.pairing.schemas import CBTServerCredentialRotationResponse
from app.modules.cbt.pairing.service import CBTPairingService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(tags=["CBT Pairing"])
CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post(
    "/servers/{server_id}/rotate-credential",
    response_model=CBTServerCredentialRotationResponse,
)
async def rotate_cbt_server_key(
    server_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CBTServerCredentialRotationResponse:
    tenant_id = tenant_id_for(current_admin)
    await SubscriptionFeatureService.ensure_feature_enabled(
        db,
        tenant_id,
        FeatureCode.CBT_PAIRING,
    )
    return await CBTPairingService.rotate_server_credential(
        db=db,
        admin=current_admin,
        server_id=server_id,
    )
