from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.subscriptions.constants import PAYSTACK_PLAN_SETTING_FIELDS
from app.modules.subscriptions.models import TenantSubscription
from app.modules.subscriptions.providers.paystack import PaystackClient, PaystackProviderError
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.service import (
    SubscriptionLifecycleService,
    SubscriptionPaymentService,
)
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    SubscriptionStatus,
)


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
    def _select_customer_subscription(
        subscription: TenantSubscription,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        viable = [
            item
            for item in candidates
            if str(item.get("status") or "").lower()
            in {"active", "non-renewing", "non_renewing", "not_renew"}
        ]
        expected_plan = SubscriptionCancellationService._provider_plan_code(subscription)
        if expected_plan:
            matching = [
                item
                for item in viable
                if SubscriptionCancellationService._candidate_plan_code(item) == expected_plan
            ]
            if matching:
                viable = matching
        if not viable:
            return None
        return max(
            viable,
            key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""),
        )

    @staticmethod
    async def _recover_paystack_credentials(
        db: AsyncSession,
        subscription: TenantSubscription,
        client: PaystackClient,
    ) -> tuple[str, str, str | None]:
        provider_data: dict[str, Any] | None = None

        if subscription.provider_subscription_code:
            response = await client.fetch_subscription(code=subscription.provider_subscription_code)
            provider_data = SubscriptionPaymentService._extract_data(response)
        elif subscription.provider_customer_code:
            customer_response = await client.fetch_customer(
                email_or_code=subscription.provider_customer_code
            )
            customer_data = SubscriptionPaymentService._extract_data(customer_response)
            customer_id = customer_data.get("id")
            if customer_id is not None:
                list_response = await client.list_subscriptions(customer_id=int(customer_id))
                raw_candidates = list_response.get("data")
                candidates = (
                    [item for item in raw_candidates if isinstance(item, dict)]
                    if isinstance(raw_candidates, list)
                    else []
                )
                provider_data = SubscriptionCancellationService._select_customer_subscription(
                    subscription,
                    candidates,
                )

        if provider_data is None:
            raise ConflictException(
                "Paystack subscription details could not be synchronized. Verify the payment webhook and try again."
            )

        code = SubscriptionPaymentService._extract_subscription_code(provider_data)
        token = SubscriptionPaymentService._extract_email_token(provider_data)
        customer_code = SubscriptionPaymentService._extract_customer_code(provider_data)
        next_payment_at = SubscriptionPaymentService._extract_next_payment_at(provider_data)

        if code:
            subscription.provider_subscription_code = code
        if token:
            subscription.provider_email_token = token
        if customer_code:
            subscription.provider_customer_code = customer_code
        if isinstance(next_payment_at, datetime):
            subscription.next_payment_at = next_payment_at
            subscription.current_period_end = next_payment_at

        await SubscriptionRepository.save_subscription(
            db=db,
            subscription=subscription,
        )

        if not subscription.provider_subscription_code or not subscription.provider_email_token:
            raise ConflictException(
                "Paystack did not return the cancellation token for this subscription. Synchronize the subscription.create webhook and try again."
            )

        return (
            subscription.provider_subscription_code,
            subscription.provider_email_token,
            str(provider_data.get("status") or "").lower() or None,
        )

    @staticmethod
    async def request_cancellation(
        db: AsyncSession,
        *,
        tenant_id,
        notes: str | None = None,
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
            raise BadRequestException("Only an active paid subscription can be cancelled.")

        if subscription.provider == PaymentProvider.PAYSTACK:
            client = PaystackClient()
            provider_status: str | None = None
            try:
                if (
                    not subscription.provider_subscription_code
                    or not subscription.provider_email_token
                ):
                    (
                        code,
                        token,
                        provider_status,
                    ) = await SubscriptionCancellationService._recover_paystack_credentials(
                        db,
                        subscription,
                        client,
                    )
                else:
                    code = subscription.provider_subscription_code
                    token = subscription.provider_email_token

                if provider_status not in {
                    "non-renewing",
                    "non_renewing",
                    "not_renew",
                }:
                    await client.disable_subscription(code=code, token=token)
            except PaystackProviderError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Unable to cancel subscription renewal with Paystack.",
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
        await db.commit()
        await flush_cache_invalidation_events(db)
        return saved
