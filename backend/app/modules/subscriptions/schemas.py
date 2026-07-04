from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
    PaymentProvider,
    PaymentStatus,
    ResourceLimitCode,
    SubscriptionStatus,
)


class ResourceUsageResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    resource: ResourceLimitCode
    used: int
    limit: int | None
    remaining: int | None
    is_unlimited: bool
    limit_reached: bool


class TenantSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_code: str
    status: SubscriptionStatus
    billing_interval: BillingInterval
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_ends_at: datetime | None
    grace_ends_at: datetime | None
    cancel_at_period_end: bool
    next_payment_at: datetime | None
    provider: PaymentProvider


class SubscriptionStatusResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: uuid.UUID
    plan_code: str
    status: SubscriptionStatus
    is_write_access_allowed: bool
    current_period_end: datetime | None = None
    grace_ends_at: datetime | None = None
    provider: PaymentProvider | None = None
    subscription: TenantSubscriptionResponse | None = None


class TenantEntitlementsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    tenant_id: uuid.UUID
    plan: str
    subscription_status: SubscriptionStatus
    features: dict[FeatureCode, bool]
    limits: dict[ResourceLimitCode, int | None]
    usage: dict[ResourceLimitCode, ResourceUsageResponse]
    current_period_end: datetime | None = None
    grace_ends_at: datetime | None = None


class FeatureCheckResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    allowed: bool
    feature: FeatureCode
    plan: str
    status: SubscriptionStatus
    reason: str | None = None


class ResourceLimitCheckResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    allowed: bool
    resource: ResourceLimitCode
    plan: str
    status: SubscriptionStatus
    used: int
    limit: int | None
    remaining: int | None
    reason: str | None = None


class SubscriptionCheckoutCreate(BaseModel):
    plan_code: str
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    billing_email: EmailStr

    @field_validator("billing_interval")
    @classmethod
    def validate_monthly_only(cls, value: BillingInterval) -> BillingInterval:
        if value != BillingInterval.MONTHLY:
            raise ValueError("Only monthly billing is currently supported.")
        return value


class SubscriptionCheckoutResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    reference: str
    authorization_url: str
    access_code: str
    amount: Decimal
    amount_kobo: int
    currency: str
    plan_code: str
    billing_interval: BillingInterval


class PaymentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID | None
    provider: PaymentProvider
    status: PaymentStatus
    reference: str
    provider_transaction_id: str | None
    plan_code: str
    billing_interval: BillingInterval
    amount: Decimal
    amount_kobo: int
    currency: str
    authorization_url: str | None
    paid_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class WebhookProcessingResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    success: bool
    provider: PaymentProvider
    event_type: str
    event_key: str
    duplicate: bool = False
    message: str
