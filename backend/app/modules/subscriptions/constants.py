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

PAYSTACK_PLAN_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: "PAYSTACK_STARTER_MONTHLY_PLAN_CODE",
        BillingInterval.YEARLY: "PAYSTACK_STARTER_YEARLY_PLAN_CODE",
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: "PAYSTACK_STANDARD_MONTHLY_PLAN_CODE",
        BillingInterval.YEARLY: "PAYSTACK_STANDARD_YEARLY_PLAN_CODE",
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: "PAYSTACK_PREMIUM_MONTHLY_PLAN_CODE",
        BillingInterval.YEARLY: "PAYSTACK_PREMIUM_YEARLY_PLAN_CODE",
    },
}

PAYSTACK_AMOUNT_SETTING_FIELDS = {
    SubscriptionPlan.PLUS: {
        BillingInterval.MONTHLY: "PAYSTACK_STARTER_MONTHLY_AMOUNT_KOBO",
        BillingInterval.YEARLY: "PAYSTACK_STARTER_YEARLY_AMOUNT_KOBO",
    },
    SubscriptionPlan.PROFESSIONAL: {
        BillingInterval.MONTHLY: "PAYSTACK_STANDARD_MONTHLY_AMOUNT_KOBO",
        BillingInterval.YEARLY: "PAYSTACK_STANDARD_YEARLY_AMOUNT_KOBO",
    },
    SubscriptionPlan.ENTERPRISE: {
        BillingInterval.MONTHLY: "PAYSTACK_PREMIUM_MONTHLY_AMOUNT_KOBO",
        BillingInterval.YEARLY: "PAYSTACK_PREMIUM_YEARLY_AMOUNT_KOBO",
    },
}

WRITE_GATED_FEATURES = {
    FeatureCode.ACADEMIC_SETUP,
    FeatureCode.REPORT_CARDS,
    FeatureCode.AI_ASSISTANT,
    FeatureCode.BULK_IMPORT,
    FeatureCode.ADVANCED_ANALYTICS,
}
