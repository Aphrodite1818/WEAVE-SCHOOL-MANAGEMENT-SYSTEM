from enum import StrEnum


class FeatureCode(StrEnum):
    """Feature switches controlled by subscription plan."""

    STUDENT_MANAGEMENT = "student_management"
    TEACHER_MANAGEMENT = "teacher_management"
    PARENT_PORTAL = "parent_portal"
    ACADEMIC_SETUP = "academic_setup"
    REPORT_CARDS = "report_cards"
    NOTICES = "notices"
    ATTENDANCE = "attendance"
    GEOFENCING = "geofencing"
    ADVANCED_ANALYTICS = "advanced_analytics"
    AI_ASSISTANT = "ai_assistant"
    BULK_IMPORT = "bulk_import"
    BULK_ACADEMIC_OPERATIONS = "bulk_academic_operations"
    TENANT_BRANDING = "tenant_branding"
    CBT_PAIRING = "cbt_pairing"


class ResourceLimitCode(StrEnum):
    """Quota-style limits controlled by subscription plan."""

    STUDENTS = "students"
    TEACHERS = "teachers"
    PARENTS = "parents"
    CBT_SERVERS = "cbt_servers"


class SubscriptionStatus(StrEnum):
    """Lifecycle states for a tenant subscription."""

    TRIALING = "trialing"
    ACTIVE = "active"
    # Retained only because PostgreSQL enum values cannot be removed safely in-place.
    NON_RENEWING = "non_renewing"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BillingInterval(StrEnum):
    """Supported billing cadences."""

    TRIAL = "trial"
    TERM = "term"
    # Database-history value; no live checkout or entitlement path uses it.
    MONTHLY = "monthly"


class TermEntitlementStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"
    FAILED = "failed"


class PaymentProvider(StrEnum):
    """Supported payment providers."""

    PAYSTACK = "paystack"
    MANUAL = "manual"


class PaymentStatus(StrEnum):
    """Lifecycle states for payment attempts."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"


class SubscriptionBlockReason(StrEnum):
    """Why a subscription-gated action was denied."""

    FEATURE_NOT_INCLUDED = "feature_not_included"
    RESOURCE_LIMIT_REACHED = "resource_limit_reached"
    TENANT_NOT_FOUND = "tenant_not_found"
    SUBSCRIPTION_INACTIVE = "subscription_inactive"
