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
}

PLAN_ALIASES = {
    "free_trial": SubscriptionPlan.FREE_TRIAL,
    "plus": SubscriptionPlan.PLUS,
    "professional": SubscriptionPlan.PROFESSIONAL,
    "enterprise": SubscriptionPlan.ENTERPRISE,
}

PAID_PLAN_CODES = {
    SubscriptionPlan.PLUS,
    SubscriptionPlan.PROFESSIONAL,
    SubscriptionPlan.ENTERPRISE,
}

PAYSTACK_PLAN_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: "PAYSTACK_PLUS_MONTHLY_PLAN_CODE",
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: "PAYSTACK_PROFESSIONAL_MONTHLY_PLAN_CODE",
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: "PAYSTACK_ENTERPRISE_MONTHLY_PLAN_CODE",
    },
}

PAYSTACK_AMOUNT_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: "PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO",
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: "PAYSTACK_PROFESSIONAL_MONTHLY_AMOUNT_KOBO",
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: "PAYSTACK_ENTERPRISE_MONTHLY_AMOUNT_KOBO",
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
