# ======================================#
#      tenant_management/models.py     #
# ======================================#

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.mixins import TimestampMixin, UUIDMixin
from app.shared.base_model import Base, PUBLIC_SCHEMA
from typing import List


class TenantStatus(str, PyEnum):
    """Represent the lifecycle state of a tenant account."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"  # legacy tenant lifecycle value retained for existing rows
    EXPIRED = "expired"  # legacy subscription lifecycle value


class SubscriptionPlan(str, PyEnum):
    """Represents the subscription plan options for a tenant (school)."""

    FREE_TRIAL = "free_trial"  # legacy persisted value; runtime normalizes to Free
    FREE = "free"
    PLUS = "plus"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantVerificationStatus(str, PyEnum):
    """Represent a tenant's verification state during onboarding."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    REJECTED = "rejected"


class InstitutionType(str, PyEnum):
    """Academic structure family selected during tenant-admin onboarding."""

    PRIMARY_SCHOOL = "PRIMARY_SCHOOL"
    SECONDARY_SCHOOL = "SECONDARY_SCHOOL"


# ── 4. Tenant Model ──────────────────────────────────────────────────────────
class Tenant(UUIDMixin, TimestampMixin, Base):
    """Store tenant onboarding, subscription, and feature configuration data."""

    __tablename__ = "tenants"

    school_name: Mapped[str] = mapped_column(String(255), nullable=False)

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="URL/subdomain slug e.g. 'greenfield-lagos'. "
        "Used by tenant middleware to resolve the school.",
    )

    admission_number_prefix: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="Tenant-specific prefix used to generate student admission numbers.",
    )

    # Whatsapp number the school's bot listens on
    school_bot_whatssap_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )

    # ── Contact / location ───────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Nigeria")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Account lifecycle & billing snapshot ────────────────────────────────
    # New tenants remain INACTIVE until their admin email is verified. Billing
    # state is represented separately by ``plan`` and term entitlements.
    status: Mapped[TenantStatus] = mapped_column(
        SQLEnum(
            TenantStatus,
            name="tenantstatus",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=TenantStatus.INACTIVE,
        nullable=False,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=SubscriptionPlan.FREE,
        nullable=False,
    )
    initial_plan_intent: Mapped[SubscriptionPlan | None] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Soft-delete ──────────────────────────────────────────────────────────
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Limits / feature flags ───────────────────────────────────────────────
    max_students: Mapped[int] = mapped_column(
        Integer,
        default=500,
        nullable=False,
        comment="Legacy tenant snapshot; runtime quotas come from subscription entitlements.",
    )
    max_teachers: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    # Flexible bag for feature flags, e.g. {"whatsapp_bot": true, "stt": true}
    feature_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # ── Timezone / locale ────────────────────────────────────────────────────
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Africa/Lagos")
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")

    # ── Onboarding ───────────────────────────────────────────────────────────
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    institution_type: Mapped[InstitutionType | None] = mapped_column(
        SQLEnum(
            InstitutionType,
            name="institution_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    branches: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=None)

    verification_status: Mapped[TenantVerificationStatus] = mapped_column(
        SQLEnum(
            TenantVerificationStatus,
            name="tenantverificationstatus",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TenantVerificationStatus.PENDING_VERIFICATION,
    )

    def __repr__(self) -> str:
        """Return a string representation of the Tenant instance."""
        return f"<Tenant id={self.id} slug={self.slug!r} status={self.status}>"

    @property
    def is_active(self) -> bool:
        """Return whether active."""
        return self.status == TenantStatus.ACTIVE and not self.is_deleted

    @property
    def whatsapp_enabled(self) -> bool:
        """Return the whatsapp_enabled value for the tenant."""
        if not self.feature_flags:
            return False
        return bool(self.feature_flags.get("whatsapp_bot", False))
