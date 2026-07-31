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
    SubscriptionPlanChangeStatus,
    SubscriptionPlanChangeType,
    SubscriptionStatus,
)
from app.shared.base_model import Base, BaseModel, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin
from app.tenant_management.models import SubscriptionPlan


class TenantSubscription(BaseModel):
    """Internal subscription ledger and application source of truth."""

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
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    provider_customer_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_subscription_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_email_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        Index("ix_tenant_subscriptions_status_period_end", "status", "current_period_end"),
        Index("ix_tenant_subscriptions_status_grace_ends_at", "status", "grace_ends_at"),
        Index(
            "uq_tenant_subscriptions_provider_subscription_code",
            "provider",
            "provider_subscription_code",
            unique=True,
            postgresql_where=text("provider_subscription_code IS NOT NULL"),
        ),
    )


class SubscriptionPlanChange(BaseModel):
    """Auditable upgrade or downgrade request for one tenant."""

    __tablename__ = "subscription_plan_changes"

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    target_plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(
            SubscriptionPlan,
            name="subscriptionplan",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    change_type: Mapped[SubscriptionPlanChangeType] = mapped_column(
        SQLEnum(
            SubscriptionPlanChangeType,
            name="subscription_plan_change_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[SubscriptionPlanChangeStatus] = mapped_column(
        SQLEnum(
            SubscriptionPlanChangeStatus,
            name="subscription_plan_change_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=SubscriptionPlanChangeStatus.PENDING,
        server_default=SubscriptionPlanChangeStatus.PENDING.value,
    )
    requested_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    blockers_json: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_subscription_plan_changes_tenant_status", "tenant_id", "status"),
        Index("ix_subscription_plan_changes_effective_at", "status", "effective_at"),
        Index(
            "uq_subscription_plan_changes_open_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'scheduled', 'awaiting_payment')"),
        ),
    )


class PaymentTransaction(BaseModel):
    """Checkout attempts and recurring charge ledger."""

    __tablename__ = "payment_transactions"

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_subscriptions.id"),
        nullable=True,
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
    provider_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
    authorization_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("ix_payment_transactions_tenant_status", "tenant_id", "status"),
        Index("ix_payment_transactions_tenant_subscription", "tenant_id", "subscription_id"),
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
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_type",
            "event_key",
            name="uq_payment_webhook_events_provider_type_key",
        ),
        Index("ix_payment_webhook_events_provider_type", "provider", "event_type"),
    )
