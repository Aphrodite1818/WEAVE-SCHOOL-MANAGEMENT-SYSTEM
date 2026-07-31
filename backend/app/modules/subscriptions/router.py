from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Header, Request, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_superadmin, get_current_tenant_admin
from app.modules.subscriptions.schemas import (
    SubscriptionCancellationRequest,
    SubscriptionCheckoutCreate,
    SubscriptionCheckoutResponse,
    SubscriptionStatusResponse,
    TenantEntitlementsResponse,
    TenantSubscriptionResponse,
    WebhookProcessingResponse,
)
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionLifecycleService,
    SubscriptionPaymentService,
)
from app.modules.superadmin.models import SuperAdmin
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentSuperadmin: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]


@router.get("/current", response_model=TenantSubscriptionResponse | None)
async def get_current_subscription(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantSubscriptionResponse | None:
    return await SubscriptionFeatureService.get_current_subscription(
        db=db,
        tenant_id=current_admin.tenant_id,
    )


@router.get("/entitlements", response_model=TenantEntitlementsResponse)
async def get_subscription_entitlements(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantEntitlementsResponse:
    return await SubscriptionFeatureService.get_tenant_entitlements(
        db=db,
        tenant_id=current_admin.tenant_id,
        use_cache=True,
    )


@router.post("/cancel", response_model=TenantSubscriptionResponse)
async def cancel_current_subscription(
    payload: SubscriptionCancellationRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantSubscriptionResponse:
    _ = payload.confirmation
    subscription = await SubscriptionLifecycleService.request_cancellation(
        db=db,
        tenant_id=current_admin.tenant_id,
        notes=payload.reason,
    )
    return TenantSubscriptionResponse.model_validate(subscription)


@router.post(
    "/checkout",
    response_model=SubscriptionCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription_checkout(
    payload: SubscriptionCheckoutCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubscriptionCheckoutResponse:
    return await SubscriptionPaymentService.initialize_subscription_checkout(
        db=db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
    )


@router.get("/verify/{reference}", response_model=SubscriptionStatusResponse)
async def verify_subscription_checkout(
    reference: str,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubscriptionStatusResponse:
    from app.modules.subscriptions.repository import SubscriptionRepository

    transaction = await SubscriptionRepository.get_transaction_by_reference(
        db=db,
        reference=reference,
    )
    if transaction is None:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Payment transaction not found.")
    if transaction.tenant_id != current_admin.tenant_id:
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("You do not have access to this subscription verification result.")

    response = await SubscriptionPaymentService.verify_subscription_checkout(
        db=db,
        reference=reference,
    )
    return response


@router.post("/paystack/webhook", response_model=WebhookProcessingResponse)
async def process_paystack_webhook(
    request: Request,
    db: DbSession,
    x_paystack_signature: str | None = Header(default=None),
) -> WebhookProcessingResponse:
    body = await request.body()
    return await SubscriptionPaymentService.process_paystack_webhook(
        db=db,
        body=body,
        signature=x_paystack_signature,
    )


@router.post("/sync-expired", response_model=dict[str, int])
async def sync_expired_subscriptions(
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> dict[str, int]:
    _ = current_superadmin
    return await SubscriptionLifecycleService.sync_expired_subscriptions(db=db)
