from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    SubscriptionStatus,
    TermEntitlementStatus,
)
from app.shared.base_model import Base, BaseModel, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin
from app.tenant_management.models import SubscriptionPlan


class TenantSubscription(BaseModel):
    """Time-limited onboarding trial ledger; paid access is term-entitlement based."""

    __tablename__ = "tenant_subscriptions"

    plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(
            SubscriptionStatus,
            name="subscription_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    billing_interval: Mapped[BillingInterval] = mapped_column(
        SQLEnum(
            BillingInterval,
            name="billing_interval",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(
            PaymentProvider,
            name="payment_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentProvider.MANUAL,
        server_default=PaymentProvider.MANUAL.value,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_tenant_subscriptions_tenant_current", "tenant_id", "is_current"),
        Index(
            "uq_tenant_subscriptions_current_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index("ix_tenant_subscriptions_trial_expiry", "status", "trial_ends_at"),
    )


class PaymentTransaction(BaseModel):
    """One-time academic-term payment attempt ledger."""

    __tablename__ = "payment_transactions"

    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(
            PaymentProvider,
            name="payment_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(
            PaymentStatus,
            name="payment_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )
    reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(120))
    plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    billing_interval: Mapped[BillingInterval] = mapped_column(
        SQLEnum(
            BillingInterval,
            name="billing_interval",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="NGN", server_default="NGN"
    )
    authorization_url: Mapped[str | None] = mapped_column(Text)
    access_code: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("ix_payment_transactions_tenant_status", "tenant_id", "status"),
        Index("ix_payment_transactions_tenant_term", "tenant_id", "academic_term_id"),
    )


class TermPlanEntitlement(BaseModel):
    """One tenant's effective plan purchase or activation for one academic term."""

    __tablename__ = "term_plan_entitlements"

    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[TermEntitlementStatus] = mapped_column(
        SQLEnum(
            TermEntitlementStatus,
            name="term_entitlement_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TermEntitlementStatus.PENDING,
        server_default=TermEntitlementStatus.PENDING.value,
    )
    payment_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.payment_transactions.id", ondelete="SET NULL"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="NGN")
    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(
            PaymentProvider,
            name="payment_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentProvider.MANUAL,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safety_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(String(120))
    activated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_term_entitlements_tenant_term", "tenant_id", "academic_term_id"),
        Index(
            "uq_term_entitlements_active_term",
            "tenant_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class PaymentWebhookEvent(UUIDMixin, TimestampMixin, Base):
    """Idempotency store for inbound payment webhooks."""

    __tablename__ = "payment_webhook_events"

    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(
            PaymentProvider,
            name="payment_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_type",
            "event_key",
            name="uq_payment_webhook_events_provider_type_key",
        ),
        Index("ix_payment_webhook_events_provider_type", "provider", "event_type"),
    )
