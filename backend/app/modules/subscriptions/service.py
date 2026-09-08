from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.events import flush_cache_invalidation_events
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
from app.modules.subscriptions.models import TenantSubscription
from app.modules.subscriptions.plans import get_plan_entitlements, normalize_plan_code
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    FeatureCheckResponse,
    ResourceLimitCheckResponse,
    ResourceUsageResponse,
    SubscriptionStatusResponse,
    TenantEntitlementsResponse,
    TenantSubscriptionResponse,
)
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
    PaymentProvider,
    ResourceLimitCode,
    SubscriptionBlockReason,
    SubscriptionStatus,
)
from app.tenant_management.models import SubscriptionPlan


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ResolvedSubscriptionState:
    tenant_id: uuid.UUID
    plan_code: str
    status: SubscriptionStatus
    billing_interval: BillingInterval
    provider: PaymentProvider | None = None
    trial_ends_at: datetime | None = None
    subscription: TenantSubscription | None = None
    effective_entitlement_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID | None = None


class SubscriptionLifecycleService:
    """Legacy cleanup for historical trial rows.

    Free Trial is no longer part of runtime plan resolution. This cleanup is
    retained so existing deployments can safely age out legacy rows.
    """

    @staticmethod
    async def sync_expired_subscriptions(
        db: AsyncSession,
        *,
        as_of: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        now = as_of or _utc_now()
        expired = 0
        subscriptions = await SubscriptionRepository.get_expirable_subscriptions(
            db=db, as_of=now, limit=limit
        )
        for subscription in subscriptions:
            if subscription.plan_code != SubscriptionPlan.FREE_TRIAL:
                continue
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.expired_at = now
            subscription.is_current = False
            tenant = await SubscriptionRepository.get_tenant(db, subscription.tenant_id)
            if tenant is not None:
                tenant.plan = SubscriptionPlan.FREE
                tenant.trial_ends_at = None
                tenant.subscription_ends_at = None
            await SubscriptionFeatureService.invalidate_tenant_subscription_state(
                subscription.tenant_id, db=db
            )
            expired += 1
        await db.commit()
        await flush_cache_invalidation_events(db)
        return {"legacy_trials_expired": expired}


class SubscriptionFeatureService:
    """Central source of truth for current-term access and permanent Free."""

    @staticmethod
    def _get_cache_ttl() -> int:
        return getattr(settings, "CACHE_SHORT_TTL_SECONDS", 300)

    @staticmethod
    async def _resolve_subscription_state(
        db: AsyncSession, tenant_id: uuid.UUID
    ) -> ResolvedSubscriptionState:
        now = _utc_now()

        from app.modules.student_academics.models import AcademicTermStatus
        from app.modules.student_academics.repository import StudentAcademicRepository
        from app.modules.subscriptions.term_entitlement_service import (
            TermPlanEntitlementService,
        )

        current_terms, _ = await StudentAcademicRepository.list_terms(
            db,
            tenant_id,
            statuses={AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING},
            is_current=True,
            limit=1,
        )
        active_term = current_terms[0] if current_terms else None
        if active_term is not None:
            entitlement = await TermPlanEntitlementService.get_active(db, tenant_id, active_term.id)
            if entitlement is not None and (
                entitlement.safety_expires_at is None or entitlement.safety_expires_at > now
            ):
                return ResolvedSubscriptionState(
                    tenant_id=tenant_id,
                    plan_code=normalize_plan_code(entitlement.plan_code),
                    status=SubscriptionStatus.ACTIVE,
                    billing_interval=BillingInterval.TERM,
                    provider=entitlement.provider,
                    effective_entitlement_id=entitlement.id,
                    academic_session_id=active_term.academic_session_id,
                )

            if await SubscriptionRepository.get_tenant(db, tenant_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found.",
                )
            return ResolvedSubscriptionState(
                tenant_id=tenant_id,
                plan_code=SubscriptionPlan.FREE.value,
                status=SubscriptionStatus.ACTIVE,
                billing_interval=BillingInterval.TERM,
                provider=PaymentProvider.MANUAL,
                academic_session_id=active_term.academic_session_id,
            )

        if await SubscriptionRepository.get_tenant(db, tenant_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found.",
            )
        return ResolvedSubscriptionState(
            tenant_id=tenant_id,
            plan_code=SubscriptionPlan.FREE.value,
            status=SubscriptionStatus.ACTIVE,
            billing_interval=BillingInterval.TERM,
            provider=PaymentProvider.MANUAL,
        )

    @staticmethod
    def _state_to_subscription_response(
        state: ResolvedSubscriptionState,
    ) -> TenantSubscriptionResponse | None:
        effective_id = (
            state.subscription.id
            if state.subscription is not None
            else state.effective_entitlement_id
        )
        if effective_id is None:
            return None
        plan_code = (
            normalize_plan_code(state.subscription.plan_code)
            if state.subscription is not None
            else state.plan_code
        )
        return TenantSubscriptionResponse.model_validate(
            {
                "id": effective_id,
                "tenant_id": state.tenant_id,
                "plan_code": plan_code,
                "status": state.status,
                "billing_interval": state.billing_interval,
                "trial_ends_at": None,
                "provider": state.provider or PaymentProvider.MANUAL,
            }
        )

    @staticmethod
    async def get_current_subscription(
        db: AsyncSession, tenant_id: uuid.UUID
    ) -> TenantSubscriptionResponse | None:
        state = await SubscriptionFeatureService._resolve_subscription_state(db, tenant_id)
        return SubscriptionFeatureService._state_to_subscription_response(state)

    @staticmethod
    async def get_subscription_status(
        db: AsyncSession, tenant_id: uuid.UUID, *, use_cache: bool = True
    ) -> SubscriptionStatusResponse:
        if use_cache and (cached := await get_cached_billing(tenant_id)) is not None:
            return SubscriptionStatusResponse.model_validate(cached)
        state = await SubscriptionFeatureService._resolve_subscription_state(db, tenant_id)
        response = SubscriptionStatusResponse(
            tenant_id=tenant_id,
            plan_code=state.plan_code,
            status=state.status,
            is_write_access_allowed=True,
            trial_ends_at=None,
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
        academic_session_id: uuid.UUID | None = None,
        use_cache: bool = True,
    ) -> int:
        cacheable = use_cache and academic_session_id is None
        if cacheable:
            cached = await get_cached_resource_usage(tenant_id=tenant_id, resource=resource)
            if cached is not None:
                return cached
        value = await SubscriptionRepository.get_resource_usage(
            db,
            tenant_id,
            resource,
            academic_session_id=academic_session_id,
        )
        if cacheable:
            await set_cached_resource_usage(
                tenant_id=tenant_id,
                resource=resource,
                value=value,
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )
        return value

    @staticmethod
    async def get_all_resource_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        use_cache: bool = True,
    ) -> dict[ResourceLimitCode, int]:
        cacheable = use_cache and academic_session_id is None
        if cacheable and (cached := await get_cached_all_resource_usage(tenant_id)) is not None:
            return {ResourceLimitCode(str(key)): int(value) for key, value in cached.items()}
        usage = await SubscriptionRepository.get_all_resource_usage(
            db,
            tenant_id,
            academic_session_id=academic_session_id,
        )
        if cacheable:
            await set_cached_all_resource_usage(
                tenant_id=tenant_id,
                value=usage,
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )
        return usage

    @staticmethod
    async def get_tenant_entitlements(
        db: AsyncSession, tenant_id: uuid.UUID, *, use_cache: bool = True
    ) -> TenantEntitlementsResponse:
        if use_cache and (cached := await get_cached_entitlements(tenant_id)) is not None:
            return TenantEntitlementsResponse.model_validate(cached)
        state = await SubscriptionFeatureService._resolve_subscription_state(db, tenant_id)
        entitlements = get_plan_entitlements(state.plan_code)
        counts = await SubscriptionFeatureService.get_all_resource_usage(
            db,
            tenant_id,
            academic_session_id=state.academic_session_id,
            use_cache=use_cache,
        )
        usage = {
            resource: SubscriptionFeatureService._build_resource_usage_response(
                resource=resource, used=counts.get(resource, 0), limit=limit
            )
            for resource, limit in entitlements.limits.items()
        }
        response = TenantEntitlementsResponse(
            tenant_id=tenant_id,
            plan=state.plan_code,
            subscription_status=state.status,
            features=entitlements.features,
            limits=entitlements.limits,
            usage=usage,
            trial_ends_at=None,
        )
        if use_cache:
            await set_cached_entitlements(
                tenant_id=tenant_id,
                value=response.model_dump(mode="json"),
                ttl=SubscriptionFeatureService._get_cache_ttl(),
            )
        return response

    @staticmethod
    def _build_resource_usage_response(
        *, resource: ResourceLimitCode, used: int, limit: int | None
    ) -> ResourceUsageResponse:
        return ResourceUsageResponse(
            resource=resource,
            used=used,
            limit=limit,
            remaining=None if limit is None else max(limit - used, 0),
            is_unlimited=limit is None,
            limit_reached=False if limit is None else used >= limit,
        )

    @staticmethod
    async def check_feature(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        feature: FeatureCode,
        *,
        use_cache: bool = True,
    ) -> FeatureCheckResponse:
        state = await SubscriptionFeatureService._resolve_subscription_state(db, tenant_id)
        allowed = get_plan_entitlements(state.plan_code).features.get(feature, False)
        return FeatureCheckResponse(
            allowed=allowed,
            feature=feature,
            plan=state.plan_code,
            status=state.status,
            reason=None if allowed else SubscriptionBlockReason.FEATURE_NOT_INCLUDED.value,
        )

    @staticmethod
    async def ensure_feature_enabled(
        db: AsyncSession, tenant_id: uuid.UUID, feature: FeatureCode
    ) -> None:
        check = await SubscriptionFeatureService.check_feature(db, tenant_id, feature)
        if check.allowed:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "This feature is not available on your current plan.",
                "feature": feature.value,
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
        state = await SubscriptionFeatureService._resolve_subscription_state(db, tenant_id)
        limit = get_plan_entitlements(state.plan_code).limits.get(resource)
        used = await SubscriptionFeatureService.get_resource_usage(
            db,
            tenant_id,
            resource,
            academic_session_id=state.academic_session_id,
            use_cache=use_cache,
        )
        remaining = None if limit is None else max(limit - used, 0)
        allowed = limit is None or used + increment <= limit
        return ResourceLimitCheckResponse(
            allowed=allowed,
            resource=resource,
            plan=state.plan_code,
            status=state.status,
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
            db, tenant_id, resource, increment=increment
        )
        if check.allowed:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": f"Your current plan has reached its {resource.value} limit.",
                "code": "PLAN_RESOURCE_LIMIT_REACHED",
                "resource": resource.value,
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
        tenant_id: uuid.UUID, db: AsyncSession | None = None
    ) -> int:
        return await invalidate_tenant_subscription_cache(tenant_id, db=db)
