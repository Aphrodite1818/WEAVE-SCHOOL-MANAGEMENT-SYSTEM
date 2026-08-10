from __future__ import annotations

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, HTTPException, status

from app.config.settings import EnvironmentType, settings
from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_superadmin
from app.modules.simulation.schemas import (
    SubscriptionSimulationRequest,
    SubscriptionSimulationResponse,
    SubscriptionSimulationState,
    SubscriptionReconcileResponse,
)
from app.modules.simulation.simulation_subscription import SubscriptionSimulationService
from app.modules.superadmin.models import SuperAdmin

router = APIRouter(prefix="/simulations", tags=["Superadmin Simulations"])
SuperadminActor: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]


def _require_staging() -> None:
    if settings.ENV != EnvironmentType.STAGING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get(
    "/subscriptions/{tenant_id}",
    response_model=SubscriptionSimulationState,
)
async def get_subscription_simulation_state(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> SubscriptionSimulationState:
    _ = current_superadmin
    _require_staging()
    return await SubscriptionSimulationService.get_state(db, tenant_id=tenant_id)


@router.post(
    "/subscriptions/{tenant_id}",
    response_model=SubscriptionSimulationResponse,
)
async def simulate_subscription(
    tenant_id: uuid.UUID,
    payload: SubscriptionSimulationRequest,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> SubscriptionSimulationResponse:
    _ = current_superadmin
    _require_staging()
    return await SubscriptionSimulationService.simulate(
        db,
        tenant_id=tenant_id,
        payload=payload,
    )


@router.post(
    "/subscriptions/{tenant_id}/reconcile",
    response_model=SubscriptionReconcileResponse,
)
async def reconcile_subscription_simulation(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> SubscriptionReconcileResponse:
    _ = current_superadmin
    _require_staging()
    return await SubscriptionSimulationService.reconcile(db, tenant_id=tenant_id)


@router.post(
    "/subscriptions/{tenant_id}/reset",
    response_model=SubscriptionSimulationResponse,
)
async def reset_subscription_simulation(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_superadmin: SuperadminActor,
) -> SubscriptionSimulationResponse:
    _ = current_superadmin
    _require_staging()
    return await SubscriptionSimulationService.reset(db, tenant_id=tenant_id)
