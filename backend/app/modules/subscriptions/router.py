from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    CurrentActor,
    get_current_actor,
    get_current_superadmin,
    get_current_tenant_admin,
)
from app.core.exceptions import ConflictException, ForbiddenException
from app.modules.simulation.router import router as simulation_router
from app.modules.subscriptions.catalogue import (
    PublicSubscriptionCatalogue,
    PublicSubscriptionCatalogueService,
)
from app.modules.subscriptions.models import TermPlanEntitlement
from app.modules.subscriptions.payment_integrity import (
    _transaction_for_update as lock_payment_transaction,
)
from app.modules.subscriptions.payment_integrity import process_paystack_webhook_secure
from app.modules.subscriptions.payment_settlement import settle_verified_term_payment
from app.modules.subscriptions.providers.paystack import PaystackClient
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    FreeTermActivationRequest,
    PaidTermCheckoutCreate,
    PaymentTransactionListResponse,
    PaymentTransactionResponse,
    SubscriptionCheckoutResponse,
    TenantEntitlementsResponse,
    TenantSubscriptionResponse,
    TermEntitlementResponse,
    TermPlanChangeRequest,
    TermPlanOptionsResponse,
    WebhookProcessingResponse,
)
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionLifecycleService,
)
from app.modules.subscriptions.subscription_enums import PaymentStatus
from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService
from app.modules.superadmin.models import SuperAdmin
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentSuperadmin: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]
CurrentSubscriptionActor: TypeAlias = Annotated[CurrentActor, Depends(get_current_actor)]


@router.get("/terms/{term_id}/plan-options", response_model=TermPlanOptionsResponse)
async def get_term_plan_options(
    term_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TermPlanOptionsResponse:
    return await TermPlanEntitlementService.get_plan_options(
        db,
        current_admin.tenant_id,
        term_id,
    )


@router.post(
    "/terms/activate-free",
    response_model=TermEntitlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def activate_free_term_plan(
    payload: FreeTermActivationRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TermEntitlementResponse:
    _ = payload.confirmation
    return TermEntitlementResponse.model_validate(
        await TermPlanEntitlementService.activate_free(
            db,
            current_admin.tenant_id,
            payload.academic_term_id,
            current_admin.id,
        )
    )


@router.post("/terms/change-plan", response_model=TermEntitlementResponse)
async def change_term_plan(
    payload: TermPlanChangeRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TermEntitlementResponse:
    _ = payload.confirmation
    return TermEntitlementResponse.model_validate(
        await TermPlanEntitlementService.change_plan(
            db,
            current_admin.tenant_id,
            payload.academic_term_id,
            payload.target_plan,
            current_admin.id,
        )
    )


@router.post(
    "/terms/checkout",
    response_model=SubscriptionCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_term_plan_checkout(
    payload: PaidTermCheckoutCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubscriptionCheckoutResponse:
    return await TermPlanEntitlementService.initialize_paid_checkout(
        db,
        current_admin.tenant_id,
        payload.academic_term_id,
        payload.plan_code,
        current_admin.email,
    )


@router.get("/terms/verify/{reference}", response_model=TermEntitlementResponse)
async def verify_term_plan_checkout(
    reference: str,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TermEntitlementResponse:
    transaction = await lock_payment_transaction(db, reference)
    if transaction is None:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Payment transaction not found.")
    if transaction.tenant_id != current_admin.tenant_id:
        raise ForbiddenException("You do not have access to this term payment.")
    provider_response = await PaystackClient().verify_transaction(reference=reference)
    entitlement = await settle_verified_term_payment(
        db,
        transaction,
        provider_response,
    )
    if entitlement is None:
        raise ConflictException(
            "Payment was received after this checkout expired. The money is recorded, "
            "but no term plan was changed automatically. Do not retry payment; contact "
            "support so the transaction can be reconciled safely.",
            payload={
                "code": "PAYMENT_RECONCILIATION_REQUIRED",
                "reference": transaction.reference,
                "academic_term_id": str(transaction.academic_term_id),
            },
        )
    return TermEntitlementResponse.model_validate(entitlement)


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


@router.get("/terms/history", response_model=list[TermEntitlementResponse])
async def list_term_plan_history(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> list[TermEntitlementResponse]:
    rows = (
        (
            await db.execute(
                select(TermPlanEntitlement)
                .where(TermPlanEntitlement.tenant_id == current_admin.tenant_id)
                .order_by(TermPlanEntitlement.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [TermEntitlementResponse.model_validate(row) for row in rows]


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
    return await SubscriptionLifecycleService.sync_expired_subscriptions(db=db)


router.include_router(simulation_router)
