from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
)
from app.tenant_management.models import SubscriptionPlan

DEFAULT_TRIAL_DAYS = 30
DEFAULT_GRACE_DAYS = 3
DEFAULT_CURRENCY = "NGN"

BILLING_INTERVAL_DAYS = {}

PLAN_ALIASES = {
    "free_trial": SubscriptionPlan.FREE_TRIAL,
    "free": SubscriptionPlan.FREE,
    "plus": SubscriptionPlan.PLUS,
    "professional": SubscriptionPlan.PROFESSIONAL,
    "enterprise": SubscriptionPlan.ENTERPRISE,
}

PAID_PLAN_CODES = {
    SubscriptionPlan.PLUS,
    SubscriptionPlan.PROFESSIONAL,
    SubscriptionPlan.ENTERPRISE,
}

# Recurring Paystack plan codes are intentionally unsupported. Kept as an
# empty mapping only while legacy ledger readers are removed from old history.
PAYSTACK_PLAN_SETTING_FIELDS: dict = {}

PAYSTACK_AMOUNT_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.TERM: "PAYSTACK_PLUS_TERM_AMOUNT_KOBO",
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.TERM: "PAYSTACK_PROFESSIONAL_TERM_AMOUNT_KOBO",
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.TERM: "PAYSTACK_ENTERPRISE_TERM_AMOUNT_KOBO",
    },
}

WRITE_GATED_FEATURES = {
    FeatureCode.ACADEMIC_SETUP,
    FeatureCode.REPORT_CARDS,
    FeatureCode.ANNOUNCEMENTS,
    FeatureCode.AI_ASSISTANT,
    FeatureCode.BULK_IMPORT,
    FeatureCode.ADVANCED_ANALYTICS,
}
