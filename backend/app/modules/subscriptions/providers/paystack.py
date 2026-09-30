"""Compatibility adapter for subscription callers using the shared payment engine."""

from __future__ import annotations

from typing import Any

from app.modules.payments.enums import PaymentPurpose
from app.modules.payments.providers.paystack import (
    PaystackClient as SharedPaystackClient,
    PaystackProviderError,
)
from app.modules.payments.service import PaymentEngine


class PaystackClient:
    """Backward-compatible subscription adapter over shared payment infrastructure."""

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_kobo: int,
        reference: str,
        callback_url: str,
        metadata: dict[str, Any],
        plan_code: str | None = None,
    ) -> dict[str, Any]:
        if plan_code is not None:
            raise PaystackProviderError(
                "Paystack recurring plan codes are no longer supported by Weave checkout."
            )
        payment_metadata = {
            **metadata,
            "payment_purpose": PaymentPurpose.TERM_SUBSCRIPTION.value,
        }
        checkout = await PaymentEngine.initialize_checkout(
            email=email,
            amount_kobo=amount_kobo,
            reference=reference,
            callback_url=callback_url,
            metadata=payment_metadata,
        )
        return {
            "status": True,
            "data": {
                "authorization_url": checkout.authorization_url,
                "access_code": checkout.access_code,
                "reference": checkout.reference,
            },
        }

    async def verify_transaction(self, *, reference: str) -> dict[str, Any]:
        return await SharedPaystackClient().verify_transaction(reference=reference)

    def verify_webhook_signature(self, *, body: bytes, signature: str | None) -> bool:
        return SharedPaystackClient().verify_webhook_signature(
            body=body,
            signature=signature,
        )

    @staticmethod
    def parse_webhook_body(body: bytes) -> dict[str, Any]:
        return SharedPaystackClient.parse_webhook_body(body)


__all__ = ["PaystackClient", "PaystackProviderError"]
