from enum import StrEnum


class FeatureCode(StrEnum):
    """Feature switches controlled by subscription plan."""

    STUDENT_MANAGEMENT = "student_management"
    TEACHER_MANAGEMENT = "teacher_management"
    PARENT_PORTAL = "parent_portal"
    ACADEMIC_SETUP = "academic_setup"
    REPORT_CARDS = "report_cards"
    ANNOUNCEMENTS = "announcements"
    ATTENDANCE = "attendance"
    GEOFENCING = "geofencing"
    ADVANCED_ANALYTICS = "advanced_analytics"
    AI_ASSISTANT = "ai_assistant"
    BULK_IMPORT = "bulk_import"
    BULK_ACADEMIC_OPERATIONS = "bulk_academic_operations"


class ResourceLimitCode(StrEnum):
    """Quota-style limits controlled by subscription plan."""

    STUDENTS = "students"
    TEACHERS = "teachers"
    PARENTS = "parents"
    CLASSES = "classes"
    SUBJECTS = "subjects"


class SubscriptionStatus(StrEnum):
    """Lifecycle states for a tenant subscription."""

    TRIALING = "trialing"
    ACTIVE = "active"
    NON_RENEWING = "non_renewing"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BillingInterval(StrEnum):
    """Supported billing cadences."""

    MONTHLY = "monthly"


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


class SubscriptionPlanChangeType(StrEnum):
    """Direction of a requested subscription plan change."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class SubscriptionPlanChangeStatus(StrEnum):
    """Lifecycle states for a requested plan change."""

    PENDING = "pending"
    BLOCKED = "blocked"
    SCHEDULED = "scheduled"
    AWAITING_PAYMENT = "awaiting_payment"
    APPLIED = "applied"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SubscriptionBlockReason(StrEnum):
    """Why a subscription-gated action was denied."""

    FEATURE_NOT_INCLUDED = "feature_not_included"
    RESOURCE_LIMIT_REACHED = "resource_limit_reached"
    TENANT_NOT_FOUND = "tenant_not_found"
    SUBSCRIPTION_INACTIVE = "subscription_inactive"
    PLAN_CHANGE_BLOCKED = "plan_change_blocked"
