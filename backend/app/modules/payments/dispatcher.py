from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.cbt.ai.quota.payment_service import AIQuotaPaymentService
from app.modules.payments.enums import PaymentPurpose
from app.modules.payments.webhook import PaymentWebhookSettlementResult, payment_data
from app.modules.subscriptions.payment_settlement import settle_term_payment_webhook


async def settle_paystack_charge(
    db: AsyncSession,
    payload: dict[str, Any],
) -> PaymentWebhookSettlementResult:
    """Route a verified provider charge to the backend domain that owns it."""

    data = payment_data(payload)
    metadata_value = data.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    purpose = str(metadata.get("payment_purpose") or "").strip()
    reference = str(data.get("reference") or "").strip()

    if purpose == PaymentPurpose.TERM_SUBSCRIPTION.value or reference.startswith("term-"):
        return await settle_term_payment_webhook(db, payload)

    if purpose == PaymentPurpose.AI_CREDIT_PURCHASE.value or reference.startswith("ai-credit-"):
        return await AIQuotaPaymentService.settle_verified_webhook_purchase(db, payload)

    raise BadRequestException("Unknown payment reference or payment purpose.")
