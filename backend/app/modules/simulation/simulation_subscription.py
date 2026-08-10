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
    SubscriptionPlanChangeSimulationState,
    SubscriptionReconcileResponse,
    SubscriptionSimulationRequest,
    SubscriptionSimulationResponse,
    SubscriptionSimulationScenario,
    SubscriptionSimulationState,
)
from app.modules.subscriptions.plan_change_service import SubscriptionPlanChangeService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionLifecycleService,
)
from app.modules.subscriptions.subscription_enums import (
    SubscriptionPlanChangeStatus,
    SubscriptionPlanChangeType,
    SubscriptionStatus,
)
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


def _plan_change_snapshot(plan_change: Any) -> dict[str, Any]:
    return {
        "id": str(plan_change.id),
        "status": _enum_value(plan_change.status),
        "effective_at": _serialize_datetime(plan_change.effective_at),
        "failure_reason": plan_change.failure_reason,
        "usage_snapshot_json": plan_change.usage_snapshot_json or {},
        "blockers_json": plan_change.blockers_json or [],
    }


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
            return bool(
                await client.exists(SubscriptionSimulationService._snapshot_key(tenant_id))
            )
        finally:
            if temporary:
                await client.aclose()

    @staticmethod
    async def _store_snapshot_if_missing(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        subscription: Any,
        plan_change: Any | None = None,
    ) -> None:
        client, temporary = await SubscriptionSimulationService._with_redis()
        key = SubscriptionSimulationService._snapshot_key(tenant_id)
        try:
            raw_snapshot = await client.get(key)
            if raw_snapshot:
                if plan_change is None:
                    return
                snapshot = json.loads(raw_snapshot)
                if snapshot.get("plan_change") is None:
                    snapshot["plan_change"] = _plan_change_snapshot(plan_change)
                    await client.set(
                        key,
                        json.dumps(snapshot),
                        ex=_SNAPSHOT_TTL_SECONDS,
                    )
                return

            tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
            if tenant is None:
                raise HTTPException(status_code=404, detail="Tenant not found.")

            snapshot: dict[str, Any] = {
                "subscription": {
                    "id": str(subscription.id),
                    "status": _enum_value(subscription.status),
                    "current_period_start": _serialize_datetime(
                        subscription.current_period_start
                    ),
                    "current_period_end": _serialize_datetime(
                        subscription.current_period_end
                    ),
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
                    "subscription_ends_at": _serialize_datetime(
                        tenant.subscription_ends_at
                    ),
                },
                "plan_change": (
                    _plan_change_snapshot(plan_change) if plan_change is not None else None
                ),
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
    async def _get_simulated_plan_change(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Any | None:
        open_change = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
        )
        if open_change is not None:
            return open_change

        client, temporary = await SubscriptionSimulationService._with_redis()
        try:
            raw_snapshot = await client.get(
                SubscriptionSimulationService._snapshot_key(tenant_id)
            )
            if not raw_snapshot:
                return None
            snapshot = json.loads(raw_snapshot)
            original = snapshot.get("plan_change")
            if not original:
                return None
            return await SubscriptionRepository.get_plan_change_by_id(
                db,
                tenant_id=tenant_id,
                plan_change_id=uuid.UUID(original["id"]),
            )
        finally:
            if temporary:
                await client.aclose()

    @staticmethod
    async def _state(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        subscription: Any,
    ) -> SubscriptionSimulationState:
        plan_change = await SubscriptionSimulationService._get_simulated_plan_change(
            db,
            tenant_id,
        )
        plan_change_state = None
        if plan_change is not None:
            plan_change_state = SubscriptionPlanChangeSimulationState(
                plan_change_id=plan_change.id,
                current_plan_code=_enum_value(plan_change.current_plan_code),
                target_plan_code=_enum_value(plan_change.target_plan_code),
                change_type=_enum_value(plan_change.change_type),
                status=_enum_value(plan_change.status),
                effective_at=plan_change.effective_at,
                failure_reason=plan_change.failure_reason,
            )

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
            plan_change=plan_change_state,
            snapshot_available=await SubscriptionSimulationService._snapshot_exists(
                tenant_id
            ),
        )

    @staticmethod
    async def _save_local_dates(
        db: AsyncSession,
        *,
        subscription: Any,
        plan_change: Any | None = None,
    ) -> None:
        await SubscriptionRepository.save_subscription(
            db=db,
            subscription=subscription,
        )
        if plan_change is not None:
            await SubscriptionRepository.save_plan_change(db, plan_change)
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
    async def _scheduled_downgrade_for_update(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Any:
        plan_change = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if plan_change is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This tenant does not have an open scheduled plan change.",
            )
        if plan_change.change_type != SubscriptionPlanChangeType.DOWNGRADE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The tenant's open plan change is not a downgrade.",
            )
        if plan_change.status != SubscriptionPlanChangeStatus.SCHEDULED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The downgrade has already moved beyond the scheduled state. "
                    "Reset the simulation before changing its effective date again."
                ),
            )
        return plan_change

    @staticmethod
    async def simulate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: SubscriptionSimulationRequest,
    ) -> SubscriptionSimulationResponse:
        subscription = (
            await SubscriptionSimulationService._get_current_subscription_for_update(
                db,
                tenant_id,
            )
        )
        existing_plan_change = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
        )
        await SubscriptionSimulationService._store_snapshot_if_missing(
            db,
            tenant_id=tenant_id,
            subscription=subscription,
            plan_change=existing_plan_change,
        )

        now = _utc_now()
        scenario = payload.scenario
        plan_change = None

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

        elif scenario in {
            SubscriptionSimulationScenario.DOWNGRADE_EFFECTIVE_IN_DAYS,
            SubscriptionSimulationScenario.DOWNGRADE_DUE_NOW,
        }:
            plan_change = await SubscriptionSimulationService._scheduled_downgrade_for_update(
                db,
                tenant_id,
            )
            await SubscriptionSimulationService._store_snapshot_if_missing(
                db,
                tenant_id=tenant_id,
                subscription=subscription,
                plan_change=plan_change,
            )
            boundary = (
                now + timedelta(days=payload.days or 1)
                if scenario
                == SubscriptionSimulationScenario.DOWNGRADE_EFFECTIVE_IN_DAYS
                else now - timedelta(minutes=1)
            )
            subscription.current_period_end = boundary
            plan_change.effective_at = boundary
            if scenario == SubscriptionSimulationScenario.DOWNGRADE_EFFECTIVE_IN_DAYS:
                detail = (
                    f"Scheduled downgrade and subscription period now become due in "
                    f"{payload.days} day(s)."
                )
            else:
                detail = (
                    "Scheduled downgrade and subscription period were moved to one "
                    "minute in the past. Run reconciliation to process the real "
                    "downgrade boundary."
                )

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported simulation scenario.",
            )

        await SubscriptionSimulationService._save_local_dates(
            db,
            subscription=subscription,
            plan_change=plan_change,
        )
        return SubscriptionSimulationResponse(
            scenario=scenario.value,
            detail=detail,
            state=await SubscriptionSimulationService._state(
                db,
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
        subscription = (
            await SubscriptionSimulationService._get_current_subscription_for_update(
                db,
                tenant_id,
            )
        )
        plan_change = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
            for_update=True,
        )
        await SubscriptionSimulationService._store_snapshot_if_missing(
            db,
            tenant_id=tenant_id,
            subscription=subscription,
            plan_change=plan_change,
        )

        now = _utc_now()
        lifecycle = {"past_due": 0, "grace_period": 0, "expired": 0}
        plan_changes = {"awaiting_payment": 0, "blocked": 0}
        period_end = (
            subscription.trial_ends_at
            if subscription.status == SubscriptionStatus.TRIALING
            else subscription.current_period_end
        )

        if (
            subscription.status == SubscriptionStatus.TRIALING
            and period_end
            and period_end <= now
        ):
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
        elif (
            subscription.status == SubscriptionStatus.ACTIVE
            and period_end
            and period_end <= now
        ):
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

        if (
            plan_change is not None
            and plan_change.change_type == SubscriptionPlanChangeType.DOWNGRADE
            and plan_change.status == SubscriptionPlanChangeStatus.SCHEDULED
            and plan_change.effective_at is not None
            and plan_change.effective_at <= now
        ):
            usage, blockers = await SubscriptionPlanChangeService._usage_and_blockers(
                db,
                tenant_id=tenant_id,
                target_plan=plan_change.target_plan_code,
            )
            plan_change.usage_snapshot_json = {
                resource.value: count for resource, count in usage.items()
            }
            plan_change.blockers_json = [
                item.model_dump(mode="json") for item in blockers
            ]
            if blockers:
                plan_change.status = SubscriptionPlanChangeStatus.BLOCKED
                plan_change.failure_reason = (
                    "Usage exceeded the target plan at the scheduled effective date."
                )
                plan_changes["blocked"] += 1
            else:
                plan_change.status = SubscriptionPlanChangeStatus.AWAITING_PAYMENT
                plan_change.failure_reason = None
                plan_changes["awaiting_payment"] += 1
            await SubscriptionRepository.save_plan_change(db, plan_change)

        await db.commit()
        await flush_cache_invalidation_events(db)
        return SubscriptionReconcileResponse(
            detail="Tenant subscription and downgrade reconciliation completed.",
            lifecycle=lifecycle,
            plan_changes=plan_changes,
            state=await SubscriptionSimulationService._state(
                db,
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
        subscription = (
            await SubscriptionSimulationService._get_current_subscription_for_update(
                db,
                tenant_id,
            )
        )
        return await SubscriptionSimulationService._state(
            db,
            tenant_id,
            subscription,
        )

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

            subscription = (
                await SubscriptionSimulationService._get_current_subscription_for_update(
                    db,
                    tenant_id,
                )
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

            original_plan_change = snapshot.get("plan_change")
            if original_plan_change:
                plan_change = await SubscriptionRepository.get_plan_change_by_id(
                    db,
                    tenant_id=tenant_id,
                    plan_change_id=uuid.UUID(original_plan_change["id"]),
                    for_update=True,
                )
                if plan_change is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "The scheduled plan change no longer exists. Reset was "
                            "refused to avoid restoring incomplete billing state."
                        ),
                    )
                if plan_change.status not in {
                    SubscriptionPlanChangeStatus.SCHEDULED,
                    SubscriptionPlanChangeStatus.AWAITING_PAYMENT,
                    SubscriptionPlanChangeStatus.BLOCKED,
                }:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "The plan change advanced outside simulation-controlled "
                            "states. Reset was refused to protect newer billing data."
                        ),
                    )
                plan_change.status = SubscriptionPlanChangeStatus(
                    original_plan_change["status"]
                )
                plan_change.effective_at = _parse_datetime(
                    original_plan_change["effective_at"]
                )
                plan_change.failure_reason = original_plan_change["failure_reason"]
                plan_change.usage_snapshot_json = original_plan_change[
                    "usage_snapshot_json"
                ]
                plan_change.blockers_json = original_plan_change["blockers_json"]
                await SubscriptionRepository.save_plan_change(db, plan_change)

            subscription.status = SubscriptionStatus(original["status"])
            subscription.current_period_start = _parse_datetime(
                original["current_period_start"]
            )
            subscription.current_period_end = _parse_datetime(
                original["current_period_end"]
            )
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
            tenant.subscription_ends_at = _parse_datetime(
                original_tenant["subscription_ends_at"]
            )
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
                detail=(
                    "Original subscription and scheduled downgrade state restored "
                    "and simulation snapshot removed."
                ),
                state=await SubscriptionSimulationService._state(
                    db,
                    tenant_id,
                    subscription,
                ),
            )
        finally:
            if temporary:
                await client.aclose()
