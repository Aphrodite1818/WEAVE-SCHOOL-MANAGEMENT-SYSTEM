from enum import StrEnum


class PaymentProvider(StrEnum):
    """Supported payment providers."""

    PAYSTACK = "paystack"
    MANUAL = "manual"


class PaymentPurpose(StrEnum):
    """Business purpose attached to a provider transaction."""

    TERM_SUBSCRIPTION = "term_subscription"
    AI_CREDIT_PURCHASE = "ai_credit_purchase"
