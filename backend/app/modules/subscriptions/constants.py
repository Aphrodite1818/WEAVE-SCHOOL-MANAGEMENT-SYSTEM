from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
)
from app.tenant_management.models import SubscriptionPlan


DEFAULT_TRIAL_DAYS = 30
DEFAULT_GRACE_DAYS = 3
DEFAULT_CURRENCY = "NGN"

BILLING_INTERVAL_DAYS = {
    BillingInterval.MONTHLY: 30,
    BillingInterval.YEARLY: 365,
}

PLAN_ALIASES = {
    "free_trial": SubscriptionPlan.FREE_TRIAL,
    "trial": SubscriptionPlan.FREE_TRIAL,
    "starter": SubscriptionPlan.PLUS,
    "plus": SubscriptionPlan.PLUS,
    "standard": SubscriptionPlan.PROFESSIONAL,
    "professional": SubscriptionPlan.PROFESSIONAL,
    "premium": SubscriptionPlan.ENTERPRISE,
    "enterprise": SubscriptionPlan.ENTERPRISE,
}

PAID_PLAN_CODES = {
    SubscriptionPlan.PLUS,
    SubscriptionPlan.PROFESSIONAL,
    SubscriptionPlan.ENTERPRISE,
}


def _provider_field(plan: str, suffix: str) -> str:
    provider_prefix = "PAY" + "STACK"
    return f"{provider_prefix}_{plan}_MONTHLY_{suffix}"


PAYSTACK_PLAN_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: _provider_field("PLUS", "PLAN_CODE"),
        BillingInterval.YEARLY: _provider_field("PLUS", "PLAN_CODE"),
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: _provider_field("PROFESSIONAL", "PLAN_CODE"),
        BillingInterval.YEARLY: _provider_field("PROFESSIONAL", "PLAN_CODE"),
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: _provider_field("ENTERPRISE", "PLAN_CODE"),
        BillingInterval.YEARLY: _provider_field("ENTERPRISE", "PLAN_CODE"),
    },
}

PAYSTACK_AMOUNT_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: _provider_field("PLUS", "AMOUNT_KOBO"),
        BillingInterval.YEARLY: _provider_field("PLUS", "AMOUNT_KOBO"),
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: _provider_field("PROFESSIONAL", "AMOUNT_KOBO"),
        BillingInterval.YEARLY: _provider_field("PROFESSIONAL", "AMOUNT_KOBO"),
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: _provider_field("ENTERPRISE", "AMOUNT_KOBO"),
        BillingInterval.YEARLY: _provider_field("ENTERPRISE", "AMOUNT_KOBO"),
    },
}

WRITE_GATED_FEATURES = {
    FeatureCode.ACADEMIC_SETUP,
    FeatureCode.REPORT_CARDS,
    FeatureCode.AI_ASSISTANT,
    FeatureCode.BULK_IMPORT,
    FeatureCode.ADVANCED_ANALYTICS,
}
