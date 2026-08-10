from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.events import flush_cache_invalidation_events
from app.core.cache.redis import create_redis_health_client, get_redis
from app.modules.simulation.schemas import (
    SubscriptionReconcileResponse,
    SubscriptionSimulationRequest,
    SubscriptionSimulationResponse,
    SubscriptionSimulationScenario,
    SubscriptionSimulationState,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionLifecycleService,
)
from app.modules.subscriptions.subscription_enums import SubscriptionStatus
from app.tenant_management.models import SubscriptionPlan, TenantStatus

_SNAPSHOT_TTL_SECONDS = 24 * 60 * 60
_SNAPSHOT_PREFIX = "weave:simulation:subscription"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SubscriptionSimulationService:
    """Controlled staging-only subscription lifecycle simulations.

    The simulator changes only local Weave state. It never calls a payment
    provider and never exposes provider identifiers, tokens, or tenant PII.
    """

    @staticmethod
    def _snapshot_key(tenant_id: uuid.UUID) -> str:
        return f"{_SNAPSHOT_PREFIX}:{tenant_id}"

    @staticmethod
    async def _with_redis() -> tuple[Redis, bool]:
        shared = get_redis()
        if shared is not None:
            return shared, False
        temporary = await create_redis_health_client()
        if temporary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is required for safe simulation snapshots.",
            )
        return temporary, True

    @staticmethod
    async def _snapshot_exists(tenant_id: uuid.UUID) -> bool:
        client, temporary = await SubscriptionSimulationService._with_redis()
        try:
            return bool(await client.exists(SubscriptionSimulationService._snapshot_key(tenant_id)))
        finally:
            if temporary:
                await client.aclose()

    @staticmethod
    async def _store_snapshot_if_missing(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        subscription: Any,
    ) -> None:
        client, temporary = await SubscriptionSimulationService._with_redis()
        key = SubscriptionSimulationService._snapshot_key(tenant_id)
        try:
            if await client.exists(key):
                return

            tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
            if tenant is None:
                raise HTTPException(status_code=404, detail="Tenant not found.")

            snapshot = {
                "subscription": {
                    "id": str(subscription.id),
                    "status": _enum_value(subscription.status),
                    "current_period_start": _serialize_datetime(subscription.current_period_start),
                    "current_period_end": _serialize_datetime(subscription.current_period_end),
                    "trial_ends_at": _serialize_datetime(subscription.trial_ends_at),
                    "grace_ends_at": _serialize_datetime(subscription.grace_ends_at),
                    "cancel_at_period_end": bool(subscription.cancel_at_period_end),
                    "cancelled_at": _serialize_datetime(subscription.cancelled_at),
                    "expired_at": _serialize_datetime(subscription.expired_at),
                    "next_payment_at": _serialize_datetime(subscription.next_payment_at),
                },
                "tenant": {
                    "plan": _enum_value(tenant.plan),
                    "status": _enum_value(tenant.status),
                    "trial_ends_at": _serialize_datetime(tenant.trial_ends_at),
                    "subscription_ends_at": _serialize_datetime(tenant.subscription_ends_at),
                },
            }
            await client.set(key, json.dumps(snapshot), ex=_SNAPSHOT_TTL_SECONDS)
        finally:
            if temporary:
                await client.aclose()

    @staticmethod
    async def _get_current_subscription_for_update(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Any:
        subscription = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This tenant does not have a current subscription to simulate.",
            )
        return subscription

    @staticmethod
    async def _state(
        tenant_id: uuid.UUID,
        subscription: Any,
    ) -> SubscriptionSimulationState:
        return SubscriptionSimulationState(
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            plan_code=_enum_value(subscription.plan_code),
            status=_enum_value(subscription.status),
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            grace_ends_at=subscription.grace_ends_at,
            cancel_at_period_end=bool(subscription.cancel_at_period_end),
            next_payment_at=subscription.next_payment_at,
            snapshot_available=await SubscriptionSimulationService._snapshot_exists(tenant_id),
        )

    @staticmethod
    async def _save_local_dates(
        db: AsyncSession,
        *,
        subscription: Any,
    ) -> None:
        await SubscriptionRepository.save_subscription(
            db=db,
            subscription=subscription,
        )
        await SubscriptionRepository.update_tenant_plan_snapshot(
            db=db,
            tenant_id=subscription.tenant_id,
            plan_code=subscription.plan_code,
            subscription_status=subscription.status,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
        )
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(
            subscription.tenant_id,
            db=db,
        )
        await db.commit()
        await flush_cache_invalidation_events(db)

    @staticmethod
    async def simulate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: SubscriptionSimulationRequest,
    ) -> SubscriptionSimulationResponse:
        subscription = await SubscriptionSimulationService._get_current_subscription_for_update(
            db,
            tenant_id,
        )
        await SubscriptionSimulationService._store_snapshot_if_missing(
            db,
            tenant_id=tenant_id,
            subscription=subscription,
        )

        now = _utc_now()
        scenario = payload.scenario

        if scenario == SubscriptionSimulationScenario.EXPIRES_IN_DAYS:
            period_end = now + timedelta(days=payload.days or 1)
            subscription.current_period_end = period_end
            subscription.next_payment_at = period_end
            if subscription.status == SubscriptionStatus.TRIALING:
                subscription.trial_ends_at = period_end
            detail = f"Subscription period now ends in {payload.days} day(s)."

        elif scenario == SubscriptionSimulationScenario.PERIOD_ENDED:
            period_end = now - timedelta(minutes=1)
            subscription.current_period_end = period_end
            subscription.next_payment_at = period_end
            if subscription.status == SubscriptionStatus.TRIALING:
                subscription.trial_ends_at = period_end
            detail = (
                "Subscription period was moved to one minute in the past. "
                "Run reconciliation to apply the real lifecycle transition."
            )

        elif scenario in {
            SubscriptionSimulationScenario.GRACE_EXPIRES_IN_DAYS,
            SubscriptionSimulationScenario.GRACE_EXPIRED,
        }:
            if subscription.status not in {
                SubscriptionStatus.PAST_DUE,
                SubscriptionStatus.GRACE_PERIOD,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Move the subscription into past-due/grace state before "
                        "adjusting grace expiry."
                    ),
                )
            if scenario == SubscriptionSimulationScenario.GRACE_EXPIRES_IN_DAYS:
                subscription.grace_ends_at = now + timedelta(days=payload.days or 1)
                detail = f"Grace period now ends in {payload.days} day(s)."
            else:
                subscription.grace_ends_at = now - timedelta(minutes=1)
                detail = (
                    "Grace period was moved to one minute in the past. "
                    "Run reconciliation to expire it."
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported simulation scenario.",
            )

        await SubscriptionSimulationService._save_local_dates(
            db,
            subscription=subscription,
        )
        return SubscriptionSimulationResponse(
            scenario=scenario.value,
            detail=detail,
            state=await SubscriptionSimulationService._state(
                tenant_id,
                subscription,
            ),
        )

    @staticmethod
    async def reconcile(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> SubscriptionReconcileResponse:
        subscription = await SubscriptionSimulationService._get_current_subscription_for_update(
            db,
            tenant_id,
        )
        await SubscriptionSimulationService._store_snapshot_if_missing(
            db,
            tenant_id=tenant_id,
            subscription=subscription,
        )

        now = _utc_now()
        lifecycle = {"past_due": 0, "grace_period": 0, "expired": 0}
        period_end = (
            subscription.trial_ends_at
            if subscription.status == SubscriptionStatus.TRIALING
            else subscription.current_period_end
        )

        if subscription.status == SubscriptionStatus.TRIALING and period_end and period_end <= now:
            subscription = await SubscriptionLifecycleService.expire_subscription(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: trial period elapsed.",
            )
            lifecycle["expired"] += 1
        elif (
            subscription.status == SubscriptionStatus.NON_RENEWING
            and period_end
            and period_end <= now
        ):
            subscription = await SubscriptionLifecycleService.expire_subscription(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: non-renewing period elapsed.",
            )
            lifecycle["expired"] += 1
        elif subscription.status == SubscriptionStatus.ACTIVE and period_end and period_end <= now:
            subscription = await SubscriptionLifecycleService.mark_past_due(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: billing period elapsed.",
            )
            lifecycle["past_due"] += 1
            subscription = await SubscriptionLifecycleService.move_to_grace_period(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: grace period applied.",
            )
            lifecycle["grace_period"] += 1
        elif subscription.status == SubscriptionStatus.PAST_DUE:
            subscription = await SubscriptionLifecycleService.move_to_grace_period(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: moved to grace period.",
            )
            lifecycle["grace_period"] += 1

        if (
            subscription.status == SubscriptionStatus.GRACE_PERIOD
            and subscription.grace_ends_at
            and subscription.grace_ends_at <= now
        ):
            subscription = await SubscriptionLifecycleService.expire_subscription(
                db=db,
                subscription=subscription,
                notes="Subscription simulation: grace period elapsed.",
            )
            lifecycle["expired"] += 1

        await db.commit()
        await flush_cache_invalidation_events(db)
        return SubscriptionReconcileResponse(
            detail="Tenant subscription reconciliation completed.",
            lifecycle=lifecycle,
            state=await SubscriptionSimulationService._state(
                tenant_id,
                subscription,
            ),
        )

    @staticmethod
    async def get_state(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> SubscriptionSimulationState:
        subscription = await SubscriptionSimulationService._get_current_subscription_for_update(
            db,
            tenant_id,
        )
        return await SubscriptionSimulationService._state(tenant_id, subscription)

    @staticmethod
    async def reset(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> SubscriptionSimulationResponse:
        client, temporary = await SubscriptionSimulationService._with_redis()
        key = SubscriptionSimulationService._snapshot_key(tenant_id)
        try:
            raw_snapshot = await client.get(key)
            if not raw_snapshot:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No simulation snapshot exists for this tenant.",
                )
            snapshot = json.loads(raw_snapshot)

            subscription = await SubscriptionSimulationService._get_current_subscription_for_update(
                db,
                tenant_id,
            )
            original = snapshot["subscription"]
            if str(subscription.id) != original["id"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The tenant's current subscription changed after the "
                        "snapshot. Reset was refused to avoid overwriting newer "
                        "subscription data."
                    ),
                )

            subscription.status = SubscriptionStatus(original["status"])
            subscription.current_period_start = _parse_datetime(original["current_period_start"])
            subscription.current_period_end = _parse_datetime(original["current_period_end"])
            subscription.trial_ends_at = _parse_datetime(original["trial_ends_at"])
            subscription.grace_ends_at = _parse_datetime(original["grace_ends_at"])
            subscription.cancel_at_period_end = bool(original["cancel_at_period_end"])
            subscription.cancelled_at = _parse_datetime(original["cancelled_at"])
            subscription.expired_at = _parse_datetime(original["expired_at"])
            subscription.next_payment_at = _parse_datetime(original["next_payment_at"])
            await SubscriptionRepository.save_subscription(
                db=db,
                subscription=subscription,
            )

            tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
            if tenant is None:
                raise HTTPException(status_code=404, detail="Tenant not found.")
            original_tenant = snapshot["tenant"]
            tenant.plan = SubscriptionPlan(original_tenant["plan"])
            tenant.status = TenantStatus(original_tenant["status"])
            tenant.trial_ends_at = _parse_datetime(original_tenant["trial_ends_at"])
            tenant.subscription_ends_at = _parse_datetime(original_tenant["subscription_ends_at"])
            await SubscriptionRepository.save_tenant(db, tenant)

            await SubscriptionFeatureService.invalidate_tenant_subscription_state(
                tenant_id,
                db=db,
            )
            await db.commit()
            await flush_cache_invalidation_events(db)
            await client.delete(key)

            return SubscriptionSimulationResponse(
                scenario="reset",
                detail=("Original subscription state restored and simulation snapshot removed."),
                state=await SubscriptionSimulationService._state(
                    tenant_id,
                    subscription,
                ),
            )
        finally:
            if temporary:
                await client.aclose()
