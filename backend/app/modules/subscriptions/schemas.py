from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    FeatureCode,
    PaymentProvider,
    PaymentStatus,
    ResourceLimitCode,
    SubscriptionStatus,
    TermEntitlementStatus,
)
from app.tenant_management.models import SubscriptionPlan


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
    trial_ends_at: datetime | None
    provider: PaymentProvider


class SubscriptionStatusResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: uuid.UUID
    plan_code: str
    status: SubscriptionStatus
    is_write_access_allowed: bool
    trial_ends_at: datetime | None = None
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
    trial_ends_at: datetime | None = None


class FeatureCheckResponse(BaseModel):
    """Internal feature-check result."""

    allowed: bool
    feature: FeatureCode
    plan: str
    status: SubscriptionStatus
    reason: str | None = None


class ResourceLimitCheckResponse(BaseModel):
    """Internal resource-limit result."""

    allowed: bool
    resource: ResourceLimitCode
    plan: str
    status: SubscriptionStatus
    used: int
    limit: int | None
    remaining: int | None
    reason: str | None = None


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
    academic_term_id: uuid.UUID
    provider: PaymentProvider
    status: PaymentStatus
    reference: str
    provider_transaction_id: str | None
    plan_code: str
    billing_interval: BillingInterval
    amount: Decimal
    amount_kobo: int
    currency: str
    paid_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class PaymentTransactionListResponse(BaseModel):
    items: list[PaymentTransactionResponse]
    total: int
    skip: int
    limit: int


class FreeTermActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    academic_term_id: uuid.UUID
    confirmation: Literal["ACTIVATE_FREE_TERM"]


class PaidTermCheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    academic_term_id: uuid.UUID
    plan_code: SubscriptionPlan

    @field_validator("plan_code")
    @classmethod
    def paid_plan_only(cls, value: SubscriptionPlan) -> SubscriptionPlan:
        if value in {SubscriptionPlan.FREE, SubscriptionPlan.FREE_TRIAL}:
            raise ValueError("Paid term checkout requires a paid plan.")
        return value


class TermEntitlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_term_id: uuid.UUID
    plan_code: SubscriptionPlan
    status: TermEntitlementStatus
    payment_transaction_id: uuid.UUID | None
    amount: Decimal
    currency: str
    provider: PaymentProvider
    activated_at: datetime | None
    closed_at: datetime | None
    expired_at: datetime | None
    safety_expires_at: datetime | None


class TermPlanActivationContext(BaseModel):
    term_id: uuid.UUID
    entitlement: TermEntitlementResponse | None
    suggested_plan: SubscriptionPlan
    payment_required: bool
    amount_kobo: int


class WebhookProcessingResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    success: bool
    provider: PaymentProvider
    event_type: str
    event_key: str
    duplicate: bool = False
    message: str
