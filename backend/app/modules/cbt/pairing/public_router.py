"""Unauthenticated CBT pairing bootstrap route."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.core.dependencies.db import DbSession
from app.modules.cbt.pairing.rate_limit import CBTPairingRateLimiter
from app.modules.cbt.pairing.schemas import PairingRequest, PairingResult
from app.modules.cbt.pairing.service import CBTPairingService
from app.modules.subscriptions.service import SubscriptionFeatureService

router = APIRouter(tags=["CBT Pairing"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/pairing/verify",
    response_model=PairingResult,
    status_code=status.HTTP_201_CREATED,
)
async def pair_server(
    payload: PairingRequest,
    request: Request,
    db: DbSession,
) -> PairingResult:
    """Exchange a one-time pairing challenge for a new tenant-owned server identity."""

    await CBTPairingRateLimiter.check(ip_address=_client_ip(request))
    result = await CBTPairingService.pair_server(db=db, payload=payload)
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(
        result.tenant.id,
        db=db,
    )
    return result
