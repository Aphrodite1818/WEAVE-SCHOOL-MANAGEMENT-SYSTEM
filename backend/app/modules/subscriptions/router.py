from __future__ import annotations

from datetime import datetime
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    CurrentActor,
    get_current_actor,
    get_current_superadmin,
    get_current_tenant_admin,
)
from app.core.exceptions import ForbiddenException
from app.modules.subscriptions.cancellation_service import (
    SubscriptionCancellationService,
)
from app.modules.subscriptions.catalogue import (
    PublicSubscriptionCatalogue,
    PublicSubscriptionCatalogueService,
)
from app.modules.subscriptions.payment_integrity import (
    process_paystack_webhook_secure,
    verify_subscription_checkout_secure,
)
from app.modules.subscriptions.plan_change_service import (
    SubscriptionPlanChangeService,
)
from app.modules.subscriptions.plan_configuration import (
    SubscriptionPlanConfigurationService,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    PaymentTransactionListResponse,
    PaymentTransactionResponse,
    SubscriptionCancellationRequest,
    SubscriptionCheckoutCreate,
    SubscriptionCheckoutResponse,
    SubscriptionPlanChangePreviewResponse,
    SubscriptionPlanChangeRequest,
    SubscriptionPlanChangeResponse,
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
from app.modules.subscriptions.subscription_enums import PaymentStatus
from app.modules.superadmin.models import SuperAdmin
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]
CurrentSuperadmin: TypeAlias = Annotated[
    SuperAdmin,
    Depends(get_current_superadmin),
]
CurrentSubscriptionActor: TypeAlias = Annotated[
    CurrentActor,
    Depends(get_current_actor),
]


@router.get("/plans", response_model=PublicSubscriptionCatalogue)
async def list_public_subscription_plans(
    request: Request,
    response: Response,
) -> PublicSubscriptionCatalogue | Response:
    catalogue = await PublicSubscriptionCatalogueService.get_catalogue()
    etag = f'"{catalogue.cache_version}"'
    cache_control = "public, no-cache, must-revalidate"
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"Cache-Control": cache_control, "ETag": etag},
        )
    response.headers["Cache-Control"] = cache_control
    response.headers["ETag"] = etag
    return catalogue


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


@router.get("/actor-entitlements", response_model=TenantEntitlementsResponse)
async def get_actor_subscription_entitlements(
    db: DbSession,
    current_actor: CurrentSubscriptionActor,
) -> TenantEntitlementsResponse:
    tenant_id = getattr(current_actor, "tenant_id", None)
    if tenant_id is None:
        raise ForbiddenException(
            "Select a tenant membership before reading subscription capabilities."
        )
    return await SubscriptionFeatureService.get_tenant_entitlements(
        db=db,
        tenant_id=tenant_id,
        use_cache=True,
    )


@router.get("/payments", response_model=PaymentTransactionListResponse)
async def list_subscription_payments(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> PaymentTransactionListResponse:
    rows, total = await SubscriptionRepository.list_payment_transactions(
        db,
        tenant_id=current_admin.tenant_id,
        status=payment_status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaymentTransactionListResponse(
        items=[PaymentTransactionResponse.model_validate(row) for row in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/plan-change/preview",
    response_model=SubscriptionPlanChangePreviewResponse,
)
async def preview_subscription_plan_change(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    target_plan_code: str = Query(min_length=2, max_length=40),
) -> SubscriptionPlanChangePreviewResponse:
    return await SubscriptionPlanChangeService.preview(
        db,
        tenant_id=current_admin.tenant_id,
        target_plan_code=target_plan_code,
    )


@router.get(
    "/plan-change/current",
    response_model=SubscriptionPlanChangeResponse | None,
)
async def get_current_subscription_plan_change(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubscriptionPlanChangeResponse | None:
    change = await SubscriptionPlanChangeService.get_open_change(
        db,
        tenant_id=current_admin.tenant_id,
    )
    if change is None:
        return None
    return SubscriptionPlanChangeResponse.model_validate(change)


@router.post(
    "/plan-change",
    response_model=SubscriptionPlanChangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_subscription_plan_change(
    payload: SubscriptionPlanChangeRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubscriptionPlanChangeResponse:
    _ = payload.confirmation
    change = await SubscriptionPlanChangeService.schedule_downgrade(
        db,
        tenant_id=current_admin.tenant_id,
        requested_by_admin_id=current_admin.id,
        target_plan_code=payload.target_plan_code,
    )
    return SubscriptionPlanChangeResponse.model_validate(change)


@router.post("/cancel", response_model=TenantSubscriptionResponse)
async def cancel_current_subscription(
    payload: SubscriptionCancellationRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantSubscriptionResponse:
    _ = payload.confirmation
    subscription = await SubscriptionCancellationService.request_cancellation(
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
    await SubscriptionPlanConfigurationService.validate_checkout_target(
        plan_code=payload.plan_code,
        billing_interval=payload.billing_interval,
    )
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
    transaction = await SubscriptionRepository.get_transaction_by_reference(
        db=db,
        reference=reference,
    )
    if transaction is None:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Payment transaction not found.")
    if transaction.tenant_id != current_admin.tenant_id:
        from app.core.exceptions import ForbiddenException as AccessForbidden

        raise AccessForbidden("You do not have access to this subscription verification result.")

    return await verify_subscription_checkout_secure(
        db=db,
        reference=reference,
    )


@router.post("/paystack/webhook", response_model=WebhookProcessingResponse)
async def process_paystack_webhook(
    request: Request,
    db: DbSession,
    x_paystack_signature: str | None = Header(default=None),
) -> WebhookProcessingResponse:
    body = await request.body()
    return await process_paystack_webhook_secure(
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
    lifecycle = await SubscriptionLifecycleService.sync_expired_subscriptions(db=db)
    plan_changes = await SubscriptionPlanChangeService.sync_due_changes(db=db)
    return {
        **lifecycle,
        "plan_changes_awaiting_payment": plan_changes["awaiting_payment"],
        "plan_changes_blocked": plan_changes["blocked"],
    }
