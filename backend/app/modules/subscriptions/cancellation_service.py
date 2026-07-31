from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.settings import settings
from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.subscriptions.constants import PAYSTACK_PLAN_SETTING_FIELDS
from app.modules.subscriptions.models import TenantSubscription
from app.modules.subscriptions.providers.paystack import (
    PaystackClient,
    PaystackProviderError,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionLifecycleService,
    SubscriptionPaymentService,
)
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    SubscriptionStatus,
)

logger = get_logger(__name__)

_PROVIDER_NON_RENEWING_STATUSES = {
    "non-renewing",
    "non_renewing",
    "not_renew",
    "complete",
    "completed",
    "cancelled",
    "canceled",
    "disabled",
}


class SubscriptionCancellationService:
    """Disable provider renewal while preserving paid access until period end."""

    @staticmethod
    def _provider_plan_code(subscription: TenantSubscription) -> str | None:
        try:
            field_name = PAYSTACK_PLAN_SETTING_FIELDS[subscription.plan_code][
                subscription.billing_interval
            ]
        except (KeyError, TypeError):
            return None
        value = getattr(settings, field_name, None)
        return str(value) if value else None

    @staticmethod
    def _candidate_plan_code(candidate: dict[str, Any]) -> str | None:
        plan = candidate.get("plan")
        if isinstance(plan, dict):
            value = plan.get("plan_code") or plan.get("code")
            return str(value) if value else None
        return None

    @staticmethod
    def _provider_status(provider_data: dict[str, Any] | None) -> str | None:
        if provider_data is None:
            return None
        value = str(provider_data.get("status") or "").strip().lower()
        return value or None

    @staticmethod
    def _select_customer_subscription(
        subscription: TenantSubscription,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        viable = [
            item
            for item in candidates
            if str(item.get("status") or "").lower()
            in ({"active", "attention"} | _PROVIDER_NON_RENEWING_STATUSES)
        ]
        expected_plan = SubscriptionCancellationService._provider_plan_code(
            subscription
        )
        if expected_plan:
            matching = [
                item
                for item in viable
                if SubscriptionCancellationService._candidate_plan_code(item)
                == expected_plan
            ]
            if matching:
                viable = matching
        if not viable:
            return None
        return max(
            viable,
            key=lambda item: str(
                item.get("updatedAt") or item.get("createdAt") or ""
            ),
        )

    @staticmethod
    async def _load_provider_subscription(
        subscription: TenantSubscription,
        client: PaystackClient,
    ) -> dict[str, Any] | None:
        if subscription.provider_subscription_code:
            response = await client.fetch_subscription(
                code=subscription.provider_subscription_code
            )
            return SubscriptionPaymentService._extract_data(response)

        if not subscription.provider_customer_code:
            return None

        customer_response = await client.fetch_customer(
            email_or_code=subscription.provider_customer_code
        )
        customer_data = SubscriptionPaymentService._extract_data(customer_response)
        customer_id = customer_data.get("id")
        if customer_id is None:
            return None
        list_response = await client.list_subscriptions(customer_id=int(customer_id))
        raw_candidates = list_response.get("data")
        candidates = (
            [item for item in raw_candidates if isinstance(item, dict)]
            if isinstance(raw_candidates, list)
            else []
        )
        return SubscriptionCancellationService._select_customer_subscription(
            subscription,
            candidates,
        )

    @staticmethod
    async def _synchronize_paystack_credentials(
        db: AsyncSession,
        subscription: TenantSubscription,
        client: PaystackClient,
    ) -> tuple[str, str, str | None]:
        provider_data = await SubscriptionCancellationService._load_provider_subscription(
            subscription,
            client,
        )
        if provider_data is None:
            raise ConflictException(
                "Paystack subscription details could not be synchronized. Verify the payment webhook and environment keys, then try again."
            )

        code = SubscriptionPaymentService._extract_subscription_code(provider_data)
        token = SubscriptionPaymentService._extract_email_token(provider_data)
        customer_code = SubscriptionPaymentService._extract_customer_code(provider_data)
        next_payment_at = SubscriptionPaymentService._extract_next_payment_at(
            provider_data
        )

        if code:
            subscription.provider_subscription_code = code
        if token:
            subscription.provider_email_token = token
        if customer_code:
            subscription.provider_customer_code = customer_code
        if isinstance(next_payment_at, datetime):
            subscription.next_payment_at = next_payment_at
            subscription.current_period_end = next_payment_at

        await SubscriptionRepository.save_subscription(db, subscription)

        if (
            not subscription.provider_subscription_code
            or not subscription.provider_email_token
        ):
            raise ConflictException(
                "Paystack did not return the cancellation credentials for this subscription. Synchronize the subscription.create webhook and try again."
            )

        return (
            subscription.provider_subscription_code,
            subscription.provider_email_token,
            SubscriptionCancellationService._provider_status(provider_data),
        )

    @staticmethod
    async def _disable_paystack_renewal(
        db: AsyncSession,
        subscription: TenantSubscription,
        client: PaystackClient,
    ) -> None:
        code, token, provider_status = (
            await SubscriptionCancellationService._synchronize_paystack_credentials(
                db,
                subscription,
                client,
            )
        )
        if provider_status in _PROVIDER_NON_RENEWING_STATUSES:
            return

        try:
            await client.disable_subscription(code=code, token=token)
            return
        except PaystackProviderError as first_error:
            logger.warning(
                "Paystack subscription disable failed; refreshing credentials before retry",
                extra={
                    "tenant_id": str(subscription.tenant_id),
                    "subscription_code": code,
                    "provider_error": str(first_error),
                },
            )

        code, token, provider_status = (
            await SubscriptionCancellationService._synchronize_paystack_credentials(
                db,
                subscription,
                client,
            )
        )
        if provider_status in _PROVIDER_NON_RENEWING_STATUSES:
            return

        await client.disable_subscription(code=code, token=token)

    @staticmethod
    async def request_cancellation(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        notes: str | None = None,
        commit: bool = True,
    ) -> TenantSubscription:
        subscription = await SubscriptionRepository.get_current_subscription(
            db=db,
            tenant_id=tenant_id,
            for_update=True,
        )
        if subscription is None:
            raise NotFoundException("No current subscription was found.")
        if (
            subscription.status == SubscriptionStatus.NON_RENEWING
            or subscription.cancel_at_period_end
        ):
            return subscription
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise BadRequestException(
                "Only an active paid subscription can disable automatic renewal."
            )

        if subscription.provider == PaymentProvider.PAYSTACK:
            reference = f"billing_{uuid.uuid4().hex[:10]}"
            try:
                await SubscriptionCancellationService._disable_paystack_renewal(
                    db,
                    subscription,
                    PaystackClient(),
                )
            except (PaystackProviderError, ConflictException) as exc:
                logger.exception(
                    "Paystack subscription cancellation failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "subscription_id": str(subscription.id),
                        "billing_reference": reference,
                        "provider_error": str(exc),
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "message": "Paystack could not disable automatic renewal.",
                        "reason": "provider_cancellation_failed",
                        "reference": reference,
                    },
                ) from exc
        elif subscription.provider != PaymentProvider.MANUAL:
            raise BadRequestException(
                "This subscription provider does not support self-service cancellation."
            )

        saved = await SubscriptionLifecycleService.mark_non_renewing(
            db=db,
            subscription=subscription,
            notes=notes or "Tenant administrator disabled automatic renewal.",
        )
        if commit:
            await db.commit()
            await flush_cache_invalidation_events(db)
        else:
            await SubscriptionFeatureService.invalidate_tenant_subscription_state(
                tenant_id,
                db=db,
            )
        return saved
