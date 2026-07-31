from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.subscriptions.models import SubscriptionPlanChange
from app.modules.subscriptions.plans import (
    coerce_subscription_plan,
    get_plan_entitlements,
    normalize_plan_code,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    PlanLimitBlocker,
    SubscriptionPlanChangePreviewResponse,
)
from app.modules.subscriptions.subscription_enums import (
    ResourceLimitCode,
    SubscriptionPlanChangeStatus,
    SubscriptionPlanChangeType,
    SubscriptionStatus,
)
from app.tenant_management.models import SubscriptionPlan


PLAN_RANK: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.FREE_TRIAL: 0,
    SubscriptionPlan.PLUS: 1,
    SubscriptionPlan.PROFESSIONAL: 2,
    SubscriptionPlan.ENTERPRISE: 3,
}


class SubscriptionPlanChangeService:
    """Validate, schedule, and reconcile safe plan transitions."""

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _change_type(
        current_plan: SubscriptionPlan,
        target_plan: SubscriptionPlan,
    ) -> SubscriptionPlanChangeType:
        return (
            SubscriptionPlanChangeType.UPGRADE
            if PLAN_RANK[target_plan] > PLAN_RANK[current_plan]
            else SubscriptionPlanChangeType.DOWNGRADE
        )

    @staticmethod
    async def _usage_and_blockers(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_plan: SubscriptionPlan,
    ) -> tuple[dict[ResourceLimitCode, int], list[PlanLimitBlocker]]:
        usage = await SubscriptionRepository.get_all_resource_usage(db, tenant_id)
        limits = get_plan_entitlements(target_plan).limits
        blockers: list[PlanLimitBlocker] = []
        for resource, used in usage.items():
            limit = limits.get(resource)
            if limit is not None and used > limit:
                blockers.append(
                    PlanLimitBlocker(
                        resource=resource,
                        used=used,
                        limit=limit,
                        excess=used - limit,
                    )
                )
        return usage, blockers

    @staticmethod
    async def preview(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_plan_code: str,
    ) -> SubscriptionPlanChangePreviewResponse:
        subscription = await SubscriptionRepository.get_current_subscription(
            db,
            tenant_id,
        )
        if subscription is None:
            raise NotFoundException("No current subscription was found.")

        current_plan = coerce_subscription_plan(subscription.plan_code)
        target_plan = coerce_subscription_plan(target_plan_code)
        if target_plan == SubscriptionPlan.FREE_TRIAL:
            raise BadRequestException("A paid subscription cannot downgrade to a new free trial.")
        if target_plan == current_plan:
            raise BadRequestException("The selected plan is already your current plan.")

        usage, blockers = await SubscriptionPlanChangeService._usage_and_blockers(
            db,
            tenant_id=tenant_id,
            target_plan=target_plan,
        )
        change_type = SubscriptionPlanChangeService._change_type(
            current_plan,
            target_plan,
        )
        effective_at = (
            subscription.current_period_end
            if change_type == SubscriptionPlanChangeType.DOWNGRADE
            else SubscriptionPlanChangeService._now()
        )
        return SubscriptionPlanChangePreviewResponse(
            current_plan_code=normalize_plan_code(current_plan),
            target_plan_code=normalize_plan_code(target_plan),
            change_type=change_type,
            eligible=not blockers,
            effective_at=effective_at,
            usage_snapshot=usage,
            blockers=blockers,
        )

    @staticmethod
    async def ensure_target_plan_eligible(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_plan: SubscriptionPlan,
    ) -> None:
        usage, blockers = await SubscriptionPlanChangeService._usage_and_blockers(
            db,
            tenant_id=tenant_id,
            target_plan=target_plan,
        )
        if not blockers:
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Your school exceeds the selected plan limits.",
                "target_plan": target_plan.value,
                "usage": {item.value: count for item, count in usage.items()},
                "blockers": [item.model_dump(mode="json") for item in blockers],
                "reason": "plan_change_blocked",
            },
        )

    @staticmethod
    async def get_open_change(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> SubscriptionPlanChange | None:
        return await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
        )

    @staticmethod
    async def schedule_downgrade(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        requested_by_admin_id: uuid.UUID,
        target_plan_code: str,
    ) -> SubscriptionPlanChange:
        subscription = await SubscriptionRepository.get_current_subscription(
            db,
            tenant_id,
            for_update=True,
        )
        if subscription is None:
            raise NotFoundException("No current subscription was found.")
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise ConflictException(
                "A downgrade can only be scheduled from an active paid subscription. Resolve any failed payment first."
            )

        current_plan = coerce_subscription_plan(subscription.plan_code)
        target_plan = coerce_subscription_plan(target_plan_code)
        if target_plan == SubscriptionPlan.FREE_TRIAL:
            raise BadRequestException("A paid subscription cannot return to a free trial.")
        if PLAN_RANK[target_plan] >= PLAN_RANK[current_plan]:
            raise BadRequestException(
                "Use checkout for upgrades. This endpoint schedules lower plans only."
            )
        if subscription.current_period_end is None:
            raise ConflictException(
                "The current billing period has no end date, so a downgrade cannot be scheduled."
            )

        existing = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if existing is not None:
            if existing.target_plan_code == target_plan:
                return existing
            raise ConflictException(
                "Another subscription plan change is already pending for this school."
            )

        usage, blockers = await SubscriptionPlanChangeService._usage_and_blockers(
            db,
            tenant_id=tenant_id,
            target_plan=target_plan,
        )
        if blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Your school exceeds the selected plan limits.",
                    "target_plan": target_plan.value,
                    "blockers": [item.model_dump(mode="json") for item in blockers],
                    "reason": "plan_change_blocked",
                },
            )

        from app.modules.subscriptions.cancellation_service import (
            SubscriptionCancellationService,
        )

        subscription = await SubscriptionCancellationService.request_cancellation(
            db,
            tenant_id=tenant_id,
            notes=(f"Automatic renewal disabled for scheduled downgrade to {target_plan.value}."),
            commit=False,
        )
        plan_change = await SubscriptionRepository.create_plan_change(
            db,
            SubscriptionPlanChange(
                tenant_id=tenant_id,
                subscription_id=subscription.id,
                current_plan_code=current_plan,
                target_plan_code=target_plan,
                change_type=SubscriptionPlanChangeType.DOWNGRADE,
                status=SubscriptionPlanChangeStatus.SCHEDULED,
                requested_by_admin_id=requested_by_admin_id,
                requested_at=SubscriptionPlanChangeService._now(),
                effective_at=subscription.current_period_end,
                usage_snapshot_json={resource.value: count for resource, count in usage.items()},
                blockers_json=[],
                provider_reference=subscription.provider_subscription_code,
            ),
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        return plan_change

    @staticmethod
    async def validate_checkout_target(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_plan: SubscriptionPlan,
    ) -> None:
        subscription = await SubscriptionRepository.get_current_subscription(
            db,
            tenant_id,
        )
        await SubscriptionPlanChangeService.ensure_target_plan_eligible(
            db,
            tenant_id=tenant_id,
            target_plan=target_plan,
        )
        if subscription is None:
            return

        current_plan = coerce_subscription_plan(subscription.plan_code)
        if PLAN_RANK[target_plan] >= PLAN_RANK[current_plan]:
            return

        pending = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
        )
        if (
            pending is None
            or pending.target_plan_code != target_plan
            or pending.status != SubscriptionPlanChangeStatus.AWAITING_PAYMENT
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        "Schedule this downgrade first. Payment for the lower "
                        "plan is accepted after the current paid period ends."
                    ),
                    "target_plan": target_plan.value,
                    "reason": "downgrade_must_be_scheduled",
                },
            )

    @staticmethod
    async def effective_resource_limit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        resource: ResourceLimitCode,
        current_limit: int | None,
    ) -> int | None:
        pending = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
        )
        if pending is None or pending.change_type != SubscriptionPlanChangeType.DOWNGRADE:
            return current_limit

        target_limit = get_plan_entitlements(pending.target_plan_code).limits.get(resource)
        if current_limit is None:
            return target_limit
        if target_limit is None:
            return current_limit
        return min(current_limit, target_limit)

    @staticmethod
    async def mark_applied(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        plan_code: SubscriptionPlan,
    ) -> None:
        pending = await SubscriptionRepository.get_open_plan_change(
            db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if pending is None or pending.target_plan_code != plan_code:
            return
        pending.status = SubscriptionPlanChangeStatus.APPLIED
        pending.applied_at = SubscriptionPlanChangeService._now()
        pending.failure_reason = None
        await SubscriptionRepository.save_plan_change(db, pending)

    @staticmethod
    async def sync_due_changes(
        db: AsyncSession,
        *,
        as_of: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        now = as_of or SubscriptionPlanChangeService._now()
        updated = {"awaiting_payment": 0, "blocked": 0}
        for change in await SubscriptionRepository.list_due_plan_changes(
            db,
            as_of=now,
            limit=limit,
        ):
            usage, blockers = await SubscriptionPlanChangeService._usage_and_blockers(
                db,
                tenant_id=change.tenant_id,
                target_plan=change.target_plan_code,
            )
            change.usage_snapshot_json = {
                resource.value: count for resource, count in usage.items()
            }
            change.blockers_json = [item.model_dump(mode="json") for item in blockers]
            if blockers:
                change.status = SubscriptionPlanChangeStatus.BLOCKED
                change.failure_reason = (
                    "Usage exceeded the target plan at the scheduled effective date."
                )
                updated["blocked"] += 1
            else:
                change.status = SubscriptionPlanChangeStatus.AWAITING_PAYMENT
                change.failure_reason = None
                updated["awaiting_payment"] += 1
            await SubscriptionRepository.save_plan_change(db, change)

        await db.commit()
        await flush_cache_invalidation_events(db)
        return updated
