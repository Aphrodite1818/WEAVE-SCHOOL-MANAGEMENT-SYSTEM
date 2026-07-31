from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.subscriptions.cache import (
    get_cached_all_resource_usage,
    get_cached_billing,
    get_cached_entitlements,
    get_cached_resource_usage,
    invalidate_tenant_subscription_cache,
    set_cached_all_resource_usage,
    set_cached_billing,
    set_cached_entitlements,
    set_cached_resource_usage,
)
from app.modules.subscriptions.constants import (
    BILLING_INTERVAL_DAYS,
    DEFAULT_GRACE_DAYS,
    DEFAULT_TRIAL_DAYS,
    PAID_PLAN_CODES,
    PAYSTACK_AMOUNT_SETTING_FIELDS,
    PAYSTACK_PLAN_SETTING_FIELDS,
)
from app.modules.subscriptions.models import PaymentTransaction, PaymentWebhookEvent, TenantSubscription
from app.modules.subscriptions.plans import coerce_subscription_plan, get_plan_entitlements, normalize_plan_code
from app.modules.subscriptions.providers.paystack import PaystackClient, PaystackProviderError
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    FeatureCheckResponse,
    PaymentTransactionResponse,
    ResourceLimitCheckResponse,
    ResourceUsageResponse,
    SubscriptionCheckoutCreate,
    SubscriptionCheckoutResponse,
    SubscriptionStatusResponse,
    TenantEntitlementsResponse,
    TenantSubscriptionResponse,
    WebhookProcessingResponse,
)
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
    PaymentProvider,
    PaymentStatus,
    ResourceLimitCode,
    SubscriptionBlockReason,
    SubscriptionStatus,
)
from app.tenant_management.models import SubscriptionPlan, TenantStatus


@dataclass(slots=True)
class ResolvedSubscriptionState:
    tenant_id: uuid.UUID
    plan_code: str
    status: SubscriptionStatus
    billing_interval: BillingInterval
    provider: PaymentProvider | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_ends_at: datetime | None
    grace_ends_at: datetime | None
    cancel_at_period_end: bool
    next_payment_at: datetime | None
    subscription: TenantSubscription | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


def _append_note(existing: str | None, note: str | None) -> str | None:
    if not note:
        return existing
    if not existing:
        return note
    return f"{existing}\n{note}"


class SubscriptionLifecycleService:
    """Subscription lifecycle transitions and expiry management."""

    @staticmethod
    def utc_now() -> datetime:
        return _utc_now()

    @staticmethod
    def calculate_period_end(
        *,
        start_at: datetime,
        billing_interval: BillingInterval,
    ) -> datetime:
        days = BILLING_INTERVAL_DAYS[billing_interval]
        return start_at + timedelta(days=days)

    @staticmethod
    async def start_trial(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        trial_days: int = DEFAULT_TRIAL_DAYS,
        notes: str | None = None,
    ) -> TenantSubscription:
        now = SubscriptionLifecycleService.utc_now()
        current = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
            for_update=True,
        )
        trial_ends_at = now + timedelta(days=trial_days)

        if current is not None and current.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.NON_RENEWING,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.GRACE_PERIOD,
        }:
            return current

        if current is not None and current.status == SubscriptionStatus.TRIALING:
            current.plan_code = SubscriptionPlan.FREE_TRIAL
            current.provider = PaymentProvider.MANUAL
            current.billing_interval = BillingInterval.MONTHLY
            current.current_period_start = now
            current.current_period_end = trial_ends_at
            current.trial_ends_at = trial_ends_at
            current.grace_ends_at = None
            current.cancel_at_period_end = False
            current.cancelled_at = None
            current.expired_at = None
            current.is_current = True
            current.notes = _append_note(current.notes, notes)
            subscription = await SubscriptionRepository.save_subscription(db=db, subscription=current)
        else:
            if current is not None:
                current.is_current = False
                await SubscriptionRepository.save_subscription(db=db, subscription=current)

            subscription = await SubscriptionRepository.create_subscription(
                db=db,
                subscription=TenantSubscription(
                    tenant_id=tenant_id,
                    plan_code=SubscriptionPlan.FREE_TRIAL,
                    status=SubscriptionStatus.TRIALING,
                    billing_interval=BillingInterval.MONTHLY,
                    provider=PaymentProvider.MANUAL,
                    current_period_start=now,
                    current_period_end=trial_ends_at,
                    trial_ends_at=trial_ends_at,
                    is_current=True,
                    notes=notes,
                ),
            )

        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=tenant_id,
            plan_code=SubscriptionPlan.FREE_TRIAL,
            subscription_status=SubscriptionStatus.TRIALING,
            current_period_end=trial_ends_at,
            trial_ends_at=trial_ends_at,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(tenant_id, db=db)
        return subscription

    @staticmethod
    async def activate_paid_subscription(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        plan_code: SubscriptionPlan,
        billing_interval: BillingInterval,
        provider: PaymentProvider,
        current_period_start: datetime | None = None,
        current_period_end: datetime | None = None,
        next_payment_at: datetime | None = None,
        provider_customer_code: str | None = None,
        provider_subscription_code: str | None = None,
        provider_email_token: str | None = None,
        payment_reference: str | None = None,
        payment_at: datetime | None = None,
        metadata_json: dict[str, Any] | None = None,
        notes: str | None = None,
        subscription_id: uuid.UUID | None = None,
    ) -> TenantSubscription:
        now = SubscriptionLifecycleService.utc_now()
        period_start = current_period_start or payment_at or now
        period_end = (
            next_payment_at
            or current_period_end
            or SubscriptionLifecycleService.calculate_period_end(
                start_at=period_start,
                billing_interval=billing_interval,
            )
        )

        current = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
            for_update=True,
        )

        target_subscription: TenantSubscription | None = None
        if current is not None:
            if subscription_id is not None and current.id == subscription_id:
                target_subscription = current
            elif (
                provider_subscription_code
                and current.provider_subscription_code == provider_subscription_code
            ):
                target_subscription = current
            elif current.plan_code == plan_code and current.provider == provider:
                target_subscription = current
            else:
                current.is_current = False
                await SubscriptionRepository.save_subscription(db=db, subscription=current)

        if target_subscription is None and subscription_id is not None:
            target_subscription = await SubscriptionRepository.get_subscription_by_id(
                db=db,
                subscription_id=subscription_id,
            )
            if target_subscription is not None:
                target_subscription.is_current = True

        if target_subscription is None:
            target_subscription = TenantSubscription(
                tenant_id=tenant_id,
                plan_code=plan_code,
                status=SubscriptionStatus.ACTIVE,
                billing_interval=billing_interval,
                provider=provider,
                current_period_start=period_start,
                current_period_end=period_end,
                is_current=True,
            )
            target_subscription = await SubscriptionRepository.create_subscription(
                db=db,
                subscription=target_subscription,
            )

        target_subscription.plan_code = plan_code
        target_subscription.status = SubscriptionStatus.ACTIVE
        target_subscription.billing_interval = billing_interval
        target_subscription.provider = provider
        target_subscription.current_period_start = period_start
        target_subscription.current_period_end = period_end
        target_subscription.trial_ends_at = None
        target_subscription.grace_ends_at = None
        target_subscription.cancel_at_period_end = False
        target_subscription.cancelled_at = None
        target_subscription.expired_at = None
        target_subscription.is_current = True
        target_subscription.provider_customer_code = provider_customer_code or target_subscription.provider_customer_code
        target_subscription.provider_subscription_code = (
            provider_subscription_code or target_subscription.provider_subscription_code
        )
        target_subscription.provider_email_token = provider_email_token or target_subscription.provider_email_token
        target_subscription.last_payment_reference = payment_reference
        target_subscription.last_payment_at = payment_at or now
        target_subscription.next_payment_at = next_payment_at or period_end
        target_subscription.metadata_json = metadata_json or target_subscription.metadata_json
        target_subscription.notes = _append_note(target_subscription.notes, notes)

        subscription = await SubscriptionRepository.save_subscription(
            db=db,
            subscription=target_subscription,
        )

        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=tenant_id,
            plan_code=plan_code,
            subscription_status=SubscriptionStatus.ACTIVE,
            current_period_end=subscription.current_period_end,
            trial_ends_at=None,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(tenant_id, db=db)
        return subscription

    @staticmethod
    async def mark_non_renewing(
        db: AsyncSession,
        *,
        subscription: TenantSubscription,
        notes: str | None = None,
    ) -> TenantSubscription:
        subscription.status = SubscriptionStatus.NON_RENEWING
        subscription.cancel_at_period_end = True
        subscription.cancelled_at = subscription.cancelled_at or SubscriptionLifecycleService.utc_now()
        subscription.notes = _append_note(subscription.notes, notes)
        saved = await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=saved.tenant_id,
            plan_code=saved.plan_code,
            subscription_status=saved.status,
            current_period_end=saved.current_period_end,
            trial_ends_at=saved.trial_ends_at,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(saved.tenant_id, db=db)
        return saved

    @staticmethod
    async def mark_past_due(
        db: AsyncSession,
        *,
        subscription: TenantSubscription,
        notes: str | None = None,
    ) -> TenantSubscription:
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.notes = _append_note(subscription.notes, notes)
        saved = await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(saved.tenant_id, db=db)
        return saved

    @staticmethod
    async def move_to_grace_period(
        db: AsyncSession,
        *,
        subscription: TenantSubscription,
        grace_days: int = DEFAULT_GRACE_DAYS,
        notes: str | None = None,
    ) -> TenantSubscription:
        now = SubscriptionLifecycleService.utc_now()
        subscription.status = SubscriptionStatus.GRACE_PERIOD
        subscription.grace_ends_at = now + timedelta(days=grace_days)
        subscription.notes = _append_note(subscription.notes, notes)
        saved = await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(saved.tenant_id, db=db)
        return saved

    @staticmethod
    async def expire_subscription(
        db: AsyncSession,
        *,
        subscription: TenantSubscription,
        notes: str | None = None,
    ) -> TenantSubscription:
        now = SubscriptionLifecycleService.utc_now()
        subscription.status = SubscriptionStatus.EXPIRED
        subscription.expired_at = now
        subscription.cancel_at_period_end = False
        subscription.notes = _append_note(subscription.notes, notes)
        saved = await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=saved.tenant_id,
            plan_code=saved.plan_code,
            subscription_status=saved.status,
            current_period_end=saved.current_period_end,
            trial_ends_at=saved.trial_ends_at,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(saved.tenant_id, db=db)
        return saved

    @staticmethod
    async def cancel_subscription(
        db: AsyncSession,
        *,
        subscription: TenantSubscription,
        notes: str | None = None,
    ) -> TenantSubscription:
        now = SubscriptionLifecycleService.utc_now()
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = now
        subscription.expired_at = now
        subscription.cancel_at_period_end = False
        subscription.notes = _append_note(subscription.notes, notes)
        saved = await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=saved.tenant_id,
            plan_code=saved.plan_code,
            subscription_status=saved.status,
            current_period_end=saved.current_period_end,
            trial_ends_at=saved.trial_ends_at,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(saved.tenant_id, db=db)
        return saved

    @staticmethod
    async def request_cancellation(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        notes: str | None = None,
    ) -> TenantSubscription:
        subscription = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if subscription is None:
            raise NotFoundException("No current subscription was found.")
        if subscription.status == SubscriptionStatus.NON_RENEWING or subscription.cancel_at_period_end:
            return subscription
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise BadRequestException("Only an active paid subscription can be cancelled.")

        if subscription.provider == PaymentProvider.PAYSTACK:
            if not subscription.provider_subscription_code or not subscription.provider_email_token:
                raise BadRequestException(
                    "This Paystack subscription is missing the provider cancellation credentials. Contact support."
                )
            try:
                await PaystackClient().disable_subscription(
                    code=subscription.provider_subscription_code,
                    token=subscription.provider_email_token,
                )
            except PaystackProviderError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to cancel subscription renewal with Paystack.",
                ) from exc
        elif subscription.provider != PaymentProvider.MANUAL:
            raise BadRequestException("This subscription provider does not support self-service cancellation.")

        return await SubscriptionLifecycleService.mark_non_renewing(
            db=db,
            subscription=subscription,
            notes=notes or "Tenant administrator disabled automatic renewal.",
        )

    @staticmethod
    async def sync_expired_subscriptions(
        db: AsyncSession,
        *,
        as_of: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        now = as_of or SubscriptionLifecycleService.utc_now()
        updated = {
            "past_due": 0,
            "grace_period": 0,
            "expired": 0,
        }

        for subscription in await SubscriptionRepository.get_expirable_subscriptions(
            db=db,
            as_of=now,
            limit=limit,
        ):
            if subscription.status == SubscriptionStatus.TRIALING:
                await SubscriptionLifecycleService.expire_subscription(
                    db=db,
                    subscription=subscription,
                    notes="Trial expired during sync.",
                )
                updated["expired"] += 1
            elif subscription.status == SubscriptionStatus.NON_RENEWING:
                await SubscriptionLifecycleService.expire_subscription(
                    db=db,
                    subscription=subscription,
                    notes="Non-renewing subscription period ended.",
                )
                updated["expired"] += 1
            elif subscription.status == SubscriptionStatus.PAST_DUE:
                await SubscriptionLifecycleService.move_to_grace_period(
                    db=db,
                    subscription=subscription,
                    notes="Past-due subscription moved to grace period during sync.",
                )
                updated["grace_period"] += 1
            else:
                await SubscriptionLifecycleService.mark_past_due(
                    db=db,
                    subscription=subscription,
                    notes="Subscription period ended without successful renewal.",
                )
                updated["past_due"] += 1
                await SubscriptionLifecycleService.move_to_grace_period(
                    db=db,
                    subscription=subscription,
                    notes="Automatic grace period applied after period end.",
                )
                updated["grace_period"] += 1

        for subscription in await SubscriptionRepository.get_grace_period_subscriptions_due_for_expiry(
            db=db,
            as_of=now,
            limit=limit,
        ):
            await SubscriptionLifecycleService.expire_subscription(
                db=db,
                subscription=subscription,
                notes="Grace period expired during sync.",
            )
            updated["expired"] += 1

        await db.commit()
        await flush_cache_invalidation_events(db)
        return updated


class SubscriptionFeatureService:
    """Resolve plans, entitlements, and status-aware write restrictions."""

    @staticmethod
    def _get_cache_ttl() -> int:
        return getattr(settings, "CACHE_SHORT_TTL_SECONDS", 300)

    @staticmethod
    def _build_resource_usage_response(
        *,
        resource: ResourceLimitCode,
        used: int,
        limit: int | None,
    ) -> ResourceUsageResponse:
        is_unlimited = limit is None
        remaining = None if is_unlimited else max(limit - used, 0)

        return ResourceUsageResponse(
            resource=resource,
            used=used,
            limit=limit,
            remaining=remaining,
            is_unlimited=is_unlimited,
            limit_reached=False if is_unlimited else used >= limit,
        )

    @staticmethod
    def _normalize_cached_usage(
        cached_usage: dict[str, int] | None,
    ) -> dict[ResourceLimitCode, int] | None:
        if cached_usage is None:
            return None

        normalized: dict[ResourceLimitCode, int] = {}
        for key, value in cached_usage.items():
            normalized[ResourceLimitCode(str(key))] = int(value)
        return normalized

    @staticmethod
    def _resolve_effective_status(state: ResolvedSubscriptionState) -> SubscriptionStatus:
        now = _utc_now()

        if state.status == SubscriptionStatus.TRIALING:
            trial_end = state.trial_ends_at or state.current_period_end
            if trial_end is not None and trial_end <= now:
                return SubscriptionStatus.EXPIRED
            return SubscriptionStatus.TRIALING

        if state.status == SubscriptionStatus.NON_RENEWING:
            if state.current_period_end is not None and state.current_period_end <= now:
                return SubscriptionStatus.EXPIRED
            return SubscriptionStatus.NON_RENEWING

        if state.status == SubscriptionStatus.ACTIVE:
            if state.current_period_end is not None and state.current_period_end <= now:
                return SubscriptionStatus.PAST_DUE
            return SubscriptionStatus.ACTIVE

        if state.status == SubscriptionStatus.PAST_DUE:
            if state.grace_ends_at is not None:
                if state.grace_ends_at <= now:
                    return SubscriptionStatus.EXPIRED
                return SubscriptionStatus.GRACE_PERIOD
            return SubscriptionStatus.PAST_DUE

        if state.status == SubscriptionStatus.GRACE_PERIOD:
            if state.grace_ends_at is not None and state.grace_ends_at <= now:
                return SubscriptionStatus.EXPIRED
            return SubscriptionStatus.GRACE_PERIOD

        return state.status

    @staticmethod
    def _is_write_access_allowed(status_value: SubscriptionStatus) -> bool:
        return status_value in {
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.NON_RENEWING,
        }

    @staticmethod
    def _state_to_subscription_response(
        state: ResolvedSubscriptionState,
    ) -> TenantSubscriptionResponse | None:
        if state.subscription is None:
            return None

        return TenantSubscriptionResponse.model_validate(
            {
                "id": state.subscription.id,
                "tenant_id": state.tenant_id,
                "plan_code": normalize_plan_code(state.subscription.plan_code),
                "status": SubscriptionFeatureService._resolve_effective_status(state),
                "billing_interval": state.billing_interval,
                "current_period_start": state.current_period_start,
                "current_period_end": state.current_period_end,
                "trial_ends_at": state.trial_ends_at,
                "grace_ends_at": state.grace_ends_at,
                "cancel_at_period_end": state.cancel_at_period_end,
                "next_payment_at": state.next_payment_at,
                "provider": state.provider or PaymentProvider.MANUAL,
            }
        )

    @staticmethod
    async def _resolve_subscription_state(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> ResolvedSubscriptionState:
        current = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
        )

        if current is not None:
            return ResolvedSubscriptionState(
                tenant_id=tenant_id,
                plan_code=normalize_plan_code(current.plan_code),
                status=current.status,
                billing_interval=current.billing_interval,
                provider=current.provider,
                current_period_start=current.current_period_start,
                current_period_end=current.current_period_end,
                trial_ends_at=current.trial_ends_at,
                grace_ends_at=current.grace_ends_at,
                cancel_at_period_end=current.cancel_at_period_end,
                next_payment_at=current.next_payment_at,
                subscription=current,
            )

        tenant = await SubscriptionRepository.get_tenant(db=db, tenant_id=tenant_id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found.",
            )

        plan_code = normalize_plan_code(tenant.plan)
        trial_ends_at = tenant.trial_ends_at
        current_period_end = tenant.subscription_ends_at or trial_ends_at
        current_status = (
            SubscriptionStatus.TRIALING
            if tenant.status == TenantStatus.TRIAL or plan_code == SubscriptionPlan.FREE_TRIAL.value
            else SubscriptionStatus.ACTIVE
        )

        return ResolvedSubscriptionState(
            tenant_id=tenant_id,
            plan_code=plan_code,
            status=current_status,
            billing_interval=BillingInterval.MONTHLY,
            provider=None,
            current_period_start=None,
            current_period_end=current_period_end,
            trial_ends_at=trial_ends_at,
            grace_ends_at=None,
            cancel_at_period_end=False,
            next_payment_at=current_period_end,
            subscription=None,
        )

    @staticmethod
    async def get_current_subscription(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> TenantSubscriptionResponse | None:
        state = await SubscriptionFeatureService._resolve_subscription_state(
            db=db,
            tenant_id=tenant_id,
        )
        return SubscriptionFeatureService._state_to_subscription_response(state)

    @staticmethod
    async def get_subscription_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        use_cache: bool = True,
    ) -> SubscriptionStatusResponse:
        if use_cache:
            cached = await get_cached_billing(tenant_id)
            if cached is not None:
                return SubscriptionStatusResponse.model_validate(cached)

        state = await SubscriptionFeatureService._resolve_subscription_state(
            db=db,
            tenant_id=tenant_id,
        )
        effective_status = SubscriptionFeatureService._resolve_effective_status(state)

        response = SubscriptionStatusResponse(
            tenant_id=tenant_id,
            plan_code=state.plan_code,
            status=effective_status,
            is_write_access_allowed=SubscriptionFeatureService._is_write_access_allowed(
                effective_status
            ),
            current_period_end=state.current_period_end,
            grace_ends_at=state.grace_ends_at,
            provider=state.provider,
            subscription=SubscriptionFeatureService._state_to_subscription_response(state),
        )

        if use_cache:
            await set_cached_billing(
                tenant_id=tenant_id,
                value=response.model_dump(mode="json"),
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )

        return response

    @staticmethod
    async def get_resource_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        resource: ResourceLimitCode,
        *,
        use_cache: bool = True,
    ) -> int:
        if use_cache:
            cached_value = await get_cached_resource_usage(
                tenant_id=tenant_id,
                resource=resource,
            )
            if cached_value is not None:
                return cached_value

        fresh_value = await SubscriptionRepository.get_resource_usage(
            db=db,
            tenant_id=tenant_id,
            resource=resource,
        )

        if use_cache:
            await set_cached_resource_usage(
                tenant_id=tenant_id,
                resource=resource,
                value=fresh_value,
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )

        return fresh_value

    @staticmethod
    async def get_all_resource_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        use_cache: bool = True,
    ) -> dict[ResourceLimitCode, int]:
        if use_cache:
            cached_usage = await get_cached_all_resource_usage(tenant_id)
            normalized_usage = SubscriptionFeatureService._normalize_cached_usage(
                cached_usage
            )
            if normalized_usage is not None:
                return normalized_usage

        fresh_usage = await SubscriptionRepository.get_all_resource_usage(
            db=db,
            tenant_id=tenant_id,
        )

        if use_cache:
            await set_cached_all_resource_usage(
                tenant_id=tenant_id,
                value=fresh_usage,
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )

        return fresh_usage

    @staticmethod
    async def get_tenant_entitlements(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        use_cache: bool = True,
    ) -> TenantEntitlementsResponse:
        if use_cache:
            cached = await get_cached_entitlements(tenant_id)
            if cached is not None:
                return TenantEntitlementsResponse.model_validate(cached)

        state = await SubscriptionFeatureService._resolve_subscription_state(
            db=db,
            tenant_id=tenant_id,
        )
        effective_status = SubscriptionFeatureService._resolve_effective_status(state)
        entitlements = get_plan_entitlements(state.plan_code)
        usage_counts = await SubscriptionFeatureService.get_all_resource_usage(
            db=db,
            tenant_id=tenant_id,
            use_cache=use_cache,
        )

        usage: dict[ResourceLimitCode, ResourceUsageResponse] = {}
        for resource, limit in entitlements.limits.items():
            used = usage_counts.get(resource, 0)
            usage[resource] = SubscriptionFeatureService._build_resource_usage_response(
                resource=resource,
                used=used,
                limit=limit,
            )

        response = TenantEntitlementsResponse(
            tenant_id=tenant_id,
            plan=state.plan_code,
            subscription_status=effective_status,
            features=entitlements.features,
            limits=entitlements.limits,
            usage=usage,
            current_period_end=state.current_period_end,
            grace_ends_at=state.grace_ends_at,
        )

        if use_cache:
            await set_cached_entitlements(
                tenant_id=tenant_id,
                value=response.model_dump(mode="json"),
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )

        return response

    @staticmethod
    async def check_feature(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        feature: FeatureCode,
        *,
        use_cache: bool = True,
    ) -> FeatureCheckResponse:
        status_response = await SubscriptionFeatureService.get_subscription_status(
            db=db,
            tenant_id=tenant_id,
            use_cache=use_cache,
        )

        if not status_response.is_write_access_allowed:
            return FeatureCheckResponse(
                allowed=False,
                feature=feature,
                plan=status_response.plan_code,
                status=status_response.status,
                reason=SubscriptionBlockReason.SUBSCRIPTION_INACTIVE.value,
            )

        entitlements = get_plan_entitlements(status_response.plan_code)
        allowed = entitlements.features.get(feature, False)
        return FeatureCheckResponse(
            allowed=allowed,
            feature=feature,
            plan=status_response.plan_code,
            status=status_response.status,
            reason=None if allowed else SubscriptionBlockReason.FEATURE_NOT_INCLUDED.value,
        )

    @staticmethod
    async def ensure_feature_enabled(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        feature: FeatureCode,
    ) -> None:
        check = await SubscriptionFeatureService.check_feature(
            db=db,
            tenant_id=tenant_id,
            feature=feature,
            use_cache=True,
        )

        if check.allowed:
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "This feature is not available on your current subscription state.",
                "feature": check.feature.value,
                "plan": check.plan,
                "status": check.status.value,
                "reason": check.reason,
            },
        )

    @staticmethod
    async def check_resource_limit(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        resource: ResourceLimitCode,
        *,
        increment: int = 1,
        use_cache: bool = False,
    ) -> ResourceLimitCheckResponse:
        if increment < 1:
            raise ValueError("increment must be greater than or equal to 1")

        status_response = await SubscriptionFeatureService.get_subscription_status(
            db=db,
            tenant_id=tenant_id,
            use_cache=use_cache,
        )

        if not status_response.is_write_access_allowed:
            return ResourceLimitCheckResponse(
                allowed=False,
                resource=resource,
                plan=status_response.plan_code,
                status=status_response.status,
                used=0,
                limit=None,
                remaining=None,
                reason=SubscriptionBlockReason.SUBSCRIPTION_INACTIVE.value,
            )

        entitlements = get_plan_entitlements(status_response.plan_code)
        limit = entitlements.limits.get(resource)
        used = await SubscriptionFeatureService.get_resource_usage(
            db=db,
            tenant_id=tenant_id,
            resource=resource,
            use_cache=use_cache,
        )

        if limit is None:
            return ResourceLimitCheckResponse(
                allowed=True,
                resource=resource,
                plan=status_response.plan_code,
                status=status_response.status,
                used=used,
                limit=None,
                remaining=None,
                reason=None,
            )

        remaining = max(limit - used, 0)
        allowed = used + increment <= limit

        return ResourceLimitCheckResponse(
            allowed=allowed,
            resource=resource,
            plan=status_response.plan_code,
            status=status_response.status,
            used=used,
            limit=limit,
            remaining=remaining,
            reason=None if allowed else SubscriptionBlockReason.RESOURCE_LIMIT_REACHED.value,
        )

    @staticmethod
    async def ensure_resource_limit_available(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        resource: ResourceLimitCode,
        *,
        increment: int = 1,
    ) -> None:
        check = await SubscriptionFeatureService.check_resource_limit(
            db=db,
            tenant_id=tenant_id,
            resource=resource,
            increment=increment,
            use_cache=False,
        )

        if check.allowed:
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Your subscription does not currently allow this write operation.",
                "resource": check.resource.value,
                "plan": check.plan,
                "status": check.status.value,
                "used": check.used,
                "limit": check.limit,
                "remaining": check.remaining,
                "reason": check.reason,
            },
        )

    @staticmethod
    async def invalidate_tenant_subscription_state(
        tenant_id: uuid.UUID,
        db: AsyncSession | None = None,
    ) -> int:
        return await invalidate_tenant_subscription_cache(tenant_id, db=db)


class SubscriptionPaymentService:
    """Billing/payment flow orchestration for subscription checkout and webhooks."""

    provider = PaystackClient()

    @staticmethod
    def _get_amount_kobo(
        plan_code: SubscriptionPlan,
        billing_interval: BillingInterval,
    ) -> int:
        field_name = PAYSTACK_AMOUNT_SETTING_FIELDS[plan_code][billing_interval]
        value = getattr(settings, field_name, None)
        if value is None:
            raise BadRequestException("Selected plan billing is not configured.")
        return int(value)

    @staticmethod
    def _get_paystack_plan_code(
        plan_code: SubscriptionPlan,
        billing_interval: BillingInterval,
    ) -> str:
        field_name = PAYSTACK_PLAN_SETTING_FIELDS[plan_code][billing_interval]
        value = getattr(settings, field_name, None)
        if not value:
            raise BadRequestException("Selected plan billing is not configured.")
        return str(value)

    @staticmethod
    def _build_reference(tenant_id: uuid.UUID) -> str:
        return f"sub_{str(tenant_id)[:8]}_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _resolve_callback_url() -> str:
        callback_url = getattr(settings, "PAYSTACK_CALLBACK_URL", None)
        if callback_url:
            return callback_url
        return f"{settings.FRONTEND_APP_URL.rstrip('/')}/billing/subscription/verify"

    @staticmethod
    def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    @staticmethod
    def _extract_metadata(data: dict[str, Any]) -> dict[str, Any]:
        metadata = data.get("metadata")
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def _extract_customer_code(data: dict[str, Any]) -> str | None:
        customer = data.get("customer")
        if isinstance(customer, dict):
            return customer.get("customer_code")
        return None

    @staticmethod
    def _extract_subscription_code(data: dict[str, Any]) -> str | None:
        subscription = data.get("subscription")
        if isinstance(subscription, dict):
            return subscription.get("subscription_code") or subscription.get("code")
        return data.get("subscription_code")

    @staticmethod
    def _extract_email_token(data: dict[str, Any]) -> str | None:
        subscription = data.get("subscription")
        if isinstance(subscription, dict):
            return subscription.get("email_token")
        return data.get("email_token")

    @staticmethod
    def _extract_next_payment_at(data: dict[str, Any]) -> datetime | None:
        return _to_utc_datetime(
            data.get("next_payment_date")
            or data.get("next_payment_at")
            or data.get("paid_until")
        )

    @staticmethod
    def _extract_event_key(event_type: str, payload: dict[str, Any]) -> str:
        data = SubscriptionPaymentService._extract_data(payload)
        for key in ("id", "reference", "subscription_code", "invoice_code", "domain"):
            value = data.get(key)
            if value is not None:
                return f"{event_type}:{value}"

        subscription = data.get("subscription")
        if isinstance(subscription, dict):
            for key in ("subscription_code", "code", "id"):
                value = subscription.get(key)
                if value is not None:
                    return f"{event_type}:{value}"

        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return f"{event_type}:{digest}"

    @staticmethod
    async def initialize_subscription_checkout(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: SubscriptionCheckoutCreate,
    ) -> SubscriptionCheckoutResponse:
        plan_code = coerce_subscription_plan(payload.plan_code)
        if plan_code not in PAID_PLAN_CODES:
            raise BadRequestException("Only paid plans require checkout.")

        billing_interval = payload.billing_interval
        amount_kobo = SubscriptionPaymentService._get_amount_kobo(
            plan_code=plan_code,
            billing_interval=billing_interval,
        )
        paystack_plan_code = SubscriptionPaymentService._get_paystack_plan_code(
            plan_code=plan_code,
            billing_interval=billing_interval,
        )
        amount = Decimal(amount_kobo) / Decimal("100")
        reference = SubscriptionPaymentService._build_reference(tenant_id)

        transaction = await SubscriptionRepository.create_pending_payment_transaction(
            db=db,
            transaction=PaymentTransaction(
                tenant_id=tenant_id,
                provider=PaymentProvider.PAYSTACK,
                status=PaymentStatus.PENDING,
                reference=reference,
                plan_code=plan_code,
                billing_interval=billing_interval,
                amount=amount,
                amount_kobo=amount_kobo,
                currency="NGN",
                raw_payload={"checkout_request": payload.model_dump(mode="json")},
            ),
        )

        metadata = {
            "tenant_id": str(tenant_id),
            "plan_code": plan_code.value,
            "billing_interval": billing_interval.value,
            "transaction_id": str(transaction.id),
        }

        try:
            provider_response = await SubscriptionPaymentService.provider.initialize_transaction(
                email=str(payload.billing_email),
                amount_kobo=amount_kobo,
                reference=reference,
                plan_code=paystack_plan_code,
                callback_url=SubscriptionPaymentService._resolve_callback_url(),
                metadata=metadata,
            )
        except PaystackProviderError as exc:
            await SubscriptionRepository.mark_transaction_failed(
                db=db,
                transaction=transaction,
                status=PaymentStatus.FAILED,
                failure_reason=str(exc),
                raw_payload={"initialize_error": str(exc)},
            )
            await db.commit()
            await flush_cache_invalidation_events(db)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to initialize subscription checkout.",
            ) from exc

        data = SubscriptionPaymentService._extract_data(provider_response)
        transaction.authorization_url = data.get("authorization_url")
        transaction.access_code = data.get("access_code")
        transaction.raw_payload = provider_response
        await SubscriptionRepository.save_payment_transaction(db=db, transaction=transaction)
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(tenant_id, db=db)
        await db.commit()
        await flush_cache_invalidation_events(db)

        return SubscriptionCheckoutResponse(
            reference=reference,
            authorization_url=str(data["authorization_url"]),
            access_code=str(data["access_code"]),
            amount=transaction.amount,
            amount_kobo=transaction.amount_kobo,
            currency=transaction.currency,
            plan_code=normalize_plan_code(plan_code),
            billing_interval=billing_interval,
        )

    @staticmethod
    async def verify_subscription_checkout(
        db: AsyncSession,
        *,
        reference: str,
    ) -> SubscriptionStatusResponse:
        transaction = await SubscriptionRepository.get_transaction_by_reference(
            db=db,
            reference=reference,
        )
        if transaction is None:
            raise NotFoundException("Payment transaction not found.")

        if transaction.status == PaymentStatus.SUCCESS:
            return await SubscriptionFeatureService.get_subscription_status(
                db=db,
                tenant_id=transaction.tenant_id,
                use_cache=False,
            )

        provider_response = await SubscriptionPaymentService.provider.verify_transaction(
            reference=reference,
        )
        data = SubscriptionPaymentService._extract_data(provider_response)
        payment_status = str(data.get("status") or "").lower()

        if payment_status != "success":
            mapped_status = (
                PaymentStatus.ABANDONED
                if payment_status in {"abandoned", "cancelled"}
                else PaymentStatus.FAILED
            )
            await SubscriptionRepository.mark_transaction_failed(
                db=db,
                transaction=transaction,
                status=mapped_status,
                failure_reason=str(data.get("gateway_response") or "Payment not successful"),
                raw_payload=provider_response,
                provider_transaction_id=str(data.get("id")) if data.get("id") is not None else None,
            )
            await db.commit()
            await flush_cache_invalidation_events(db)
            raise BadRequestException("Payment has not been completed successfully.")

        await SubscriptionPaymentService.handle_charge_success(
            db=db,
            payload=provider_response,
            transaction=transaction,
        )
        await db.commit()
        await flush_cache_invalidation_events(db)

        return await SubscriptionFeatureService.get_subscription_status(
            db=db,
            tenant_id=transaction.tenant_id,
            use_cache=False,
        )

    @staticmethod
    async def process_paystack_webhook(
        db: AsyncSession,
        *,
        body: bytes,
        signature: str | None,
    ) -> WebhookProcessingResponse:
        if not SubscriptionPaymentService.provider.verify_webhook_signature(
            body=body,
            signature=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Paystack webhook signature.",
            )

        payload = SubscriptionPaymentService.provider.parse_webhook_body(body)
        event_type = str(payload.get("event") or "unknown")
        event_key = SubscriptionPaymentService._extract_event_key(event_type, payload)

        webhook_event = await SubscriptionRepository.get_webhook_event_by_provider(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=event_key,
        )

        if webhook_event is not None and webhook_event.processed_at is not None:
            return WebhookProcessingResponse(
                success=True,
                provider=PaymentProvider.PAYSTACK,
                event_type=event_type,
                event_key=event_key,
                duplicate=True,
                message="Webhook event already processed.",
            )

        if webhook_event is None:
            webhook_event = await SubscriptionRepository.create_webhook_event(
                db=db,
                webhook_event=PaymentWebhookEvent(
                    provider=PaymentProvider.PAYSTACK,
                    event_type=event_type,
                    event_key=event_key,
                    payload=payload,
                ),
            )
        else:
            webhook_event.payload = payload

        try:
            await SubscriptionPaymentService.dispatch_paystack_event(
                db=db,
                payload=payload,
            )
            await SubscriptionRepository.mark_webhook_processed(
                db=db,
                webhook_event=webhook_event,
                processed_at=_utc_now(),
            )
            await db.commit()
            await flush_cache_invalidation_events(db)
            return WebhookProcessingResponse(
                success=True,
                provider=PaymentProvider.PAYSTACK,
                event_type=event_type,
                event_key=event_key,
                duplicate=False,
                message="Webhook event processed successfully.",
            )
        except Exception as exc:
            await SubscriptionRepository.mark_webhook_failed(
                db=db,
                webhook_event=webhook_event,
                error_message=str(exc),
            )
            await db.commit()
            await flush_cache_invalidation_events(db)
            raise

    @staticmethod
    async def dispatch_paystack_event(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        event_type = str(payload.get("event") or "")

        if event_type == "charge.success":
            await SubscriptionPaymentService.handle_charge_success(db=db, payload=payload)
            return

        if event_type == "subscription.create":
            await SubscriptionPaymentService.handle_subscription_create(db=db, payload=payload)
            return

        if event_type == "invoice.payment_failed":
            await SubscriptionPaymentService.handle_invoice_payment_failed(db=db, payload=payload)
            return

        if event_type == "subscription.not_renew":
            await SubscriptionPaymentService.handle_subscription_not_renew(db=db, payload=payload)
            return

        if event_type == "subscription.disable":
            await SubscriptionPaymentService.handle_subscription_disable(db=db, payload=payload)
            return

        if event_type == "invoice.update":
            await SubscriptionPaymentService.handle_invoice_update(db=db, payload=payload)
            return

        if event_type == "invoice.create":
            return

    @staticmethod
    async def handle_charge_success(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
        transaction: PaymentTransaction | None = None,
    ) -> TenantSubscription:
        data = SubscriptionPaymentService._extract_data(payload)
        metadata = SubscriptionPaymentService._extract_metadata(data)
        reference = data.get("reference")

        if transaction is None and reference:
            transaction = await SubscriptionRepository.get_transaction_by_reference(
                db=db,
                reference=str(reference),
            )

        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        provider_customer_code = SubscriptionPaymentService._extract_customer_code(data)

        existing_subscription = None
        if provider_subscription_code:
            existing_subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_subscription_code=provider_subscription_code,
            )
        if existing_subscription is None and provider_customer_code:
            existing_subscription = await SubscriptionRepository.find_current_subscription_by_provider_customer_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_customer_code=provider_customer_code,
            )

        tenant_id_raw = metadata.get("tenant_id")
        if transaction is not None:
            tenant_id = transaction.tenant_id
        elif existing_subscription is not None:
            tenant_id = existing_subscription.tenant_id
        elif tenant_id_raw:
            tenant_id = uuid.UUID(str(tenant_id_raw))
        else:
            raise BadRequestException("Unable to resolve tenant for charge.success event.")

        plan_source = (
            metadata.get("plan_code")
            or (transaction.plan_code.value if transaction is not None else None)
            or (existing_subscription.plan_code.value if existing_subscription is not None else None)
        )
        plan_code = coerce_subscription_plan(plan_source)

        interval_source = (
            metadata.get("billing_interval")
            or (transaction.billing_interval.value if transaction is not None else None)
            or (existing_subscription.billing_interval.value if existing_subscription is not None else None)
        )
        billing_interval = BillingInterval(str(interval_source or BillingInterval.MONTHLY.value))

        amount_kobo = int(data.get("amount") or (transaction.amount_kobo if transaction is not None else 0))
        amount = Decimal(amount_kobo) / Decimal("100")
        provider_transaction_id = str(data.get("id")) if data.get("id") is not None else None
        paid_at = _to_utc_datetime(data.get("paid_at") or data.get("transaction_date")) or _utc_now()
        next_payment_at = SubscriptionPaymentService._extract_next_payment_at(data)

        if transaction is None:
            transaction = await SubscriptionRepository.create_pending_payment_transaction(
                db=db,
                transaction=PaymentTransaction(
                    tenant_id=tenant_id,
                    provider=PaymentProvider.PAYSTACK,
                    status=PaymentStatus.SUCCESS,
                    reference=str(reference or SubscriptionPaymentService._build_reference(tenant_id)),
                    provider_transaction_id=provider_transaction_id,
                    plan_code=plan_code,
                    billing_interval=billing_interval,
                    amount=amount,
                    amount_kobo=amount_kobo,
                    currency=str(data.get("currency") or "NGN"),
                    paid_at=paid_at,
                    raw_payload=payload,
                ),
            )

        period_start = paid_at
        if (
            existing_subscription is not None
            and existing_subscription.status != SubscriptionStatus.TRIALING
            and existing_subscription.current_period_end is not None
            and existing_subscription.current_period_end > paid_at
        ):
            period_start = existing_subscription.current_period_end

        subscription = await SubscriptionLifecycleService.activate_paid_subscription(
            db=db,
            tenant_id=tenant_id,
            plan_code=plan_code,
            billing_interval=billing_interval,
            provider=PaymentProvider.PAYSTACK,
            current_period_start=period_start,
            current_period_end=next_payment_at,
            next_payment_at=next_payment_at,
            provider_customer_code=provider_customer_code,
            provider_subscription_code=provider_subscription_code,
            provider_email_token=SubscriptionPaymentService._extract_email_token(data),
            payment_reference=transaction.reference,
            payment_at=paid_at,
            metadata_json=metadata or payload,
            notes="Activated from Paystack charge.success.",
            subscription_id=existing_subscription.id if existing_subscription is not None else transaction.subscription_id,
        )

        await SubscriptionRepository.mark_transaction_success(
            db=db,
            transaction=transaction,
            provider_transaction_id=provider_transaction_id,
            subscription_id=subscription.id,
            paid_at=paid_at,
            raw_payload=payload,
        )

        return subscription

    @staticmethod
    async def handle_subscription_create(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        data = SubscriptionPaymentService._extract_data(payload)
        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        provider_customer_code = SubscriptionPaymentService._extract_customer_code(data)

        subscription = None
        if provider_subscription_code:
            subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_subscription_code=provider_subscription_code,
            )
        if subscription is None and provider_customer_code:
            subscription = await SubscriptionRepository.find_current_subscription_by_provider_customer_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_customer_code=provider_customer_code,
            )
        if subscription is None:
            return

        subscription.provider_subscription_code = provider_subscription_code or subscription.provider_subscription_code
        subscription.provider_customer_code = provider_customer_code or subscription.provider_customer_code
        subscription.provider_email_token = (
            SubscriptionPaymentService._extract_email_token(data)
            or subscription.provider_email_token
        )
        next_payment_at = SubscriptionPaymentService._extract_next_payment_at(data)
        if next_payment_at is not None:
            subscription.next_payment_at = next_payment_at
            subscription.current_period_end = next_payment_at

        await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(subscription.tenant_id, db=db)

    @staticmethod
    async def handle_invoice_payment_failed(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        data = SubscriptionPaymentService._extract_data(payload)
        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        provider_customer_code = SubscriptionPaymentService._extract_customer_code(data)

        subscription = None
        if provider_subscription_code:
            subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_subscription_code=provider_subscription_code,
            )
        if subscription is None and provider_customer_code:
            subscription = await SubscriptionRepository.find_current_subscription_by_provider_customer_code(
                db=db,
                provider=PaymentProvider.PAYSTACK,
                provider_customer_code=provider_customer_code,
            )
        if subscription is None:
            return

        await SubscriptionLifecycleService.mark_past_due(
            db=db,
            subscription=subscription,
            notes="Paystack invoice payment failed.",
        )
        await SubscriptionLifecycleService.move_to_grace_period(
            db=db,
            subscription=subscription,
            notes="Grace period started after failed invoice payment.",
        )

    @staticmethod
    async def handle_subscription_not_renew(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        data = SubscriptionPaymentService._extract_data(payload)
        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        if not provider_subscription_code:
            return

        subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            provider_subscription_code=provider_subscription_code,
        )
        if subscription is None:
            return

        await SubscriptionLifecycleService.mark_non_renewing(
            db=db,
            subscription=subscription,
            notes="Paystack marked subscription as non-renewing.",
        )

    @staticmethod
    async def handle_subscription_disable(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        data = SubscriptionPaymentService._extract_data(payload)
        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        if not provider_subscription_code:
            return

        subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            provider_subscription_code=provider_subscription_code,
        )
        if subscription is None:
            return

        await SubscriptionLifecycleService.mark_non_renewing(
            db=db,
            subscription=subscription,
            notes="Paystack disabled automatic renewal.",
        )

    @staticmethod
    async def handle_invoice_update(
        db: AsyncSession,
        *,
        payload: dict[str, Any],
    ) -> None:
        data = SubscriptionPaymentService._extract_data(payload)
        provider_subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
        if not provider_subscription_code:
            return

        subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            provider_subscription_code=provider_subscription_code,
        )
        if subscription is None:
            return

        next_payment_at = SubscriptionPaymentService._extract_next_payment_at(data)
        if next_payment_at is not None:
            subscription.next_payment_at = next_payment_at
            subscription.current_period_end = next_payment_at
            await SubscriptionRepository.save_subscription(db=db, subscription=subscription)
            await SubscriptionFeatureService.invalidate_tenant_subscription_state(subscription.tenant_id, db=db)
