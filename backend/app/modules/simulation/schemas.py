from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.tenant_management.models import SubscriptionPlan


class SubscriptionSimulationScenario(str, Enum):
    ACTIVATE_FREE = "activate_free"
    INITIALIZE_PAID = "initialize_paid"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILURE = "payment_failure"
    DUPLICATE_WEBHOOK = "duplicate_webhook"
    WRONG_AMOUNT = "wrong_amount"
    WRONG_TERM = "wrong_term"
    UPGRADE_TO_PROFESSIONAL = "upgrade_to_professional"
    CLOSE_TERM = "close_term"
    TRIAL_EXPIRED = "trial_expired"
    CLOSED_ACTIVE_RECONCILIATION = "closed_active_reconciliation"
    SAFETY_CAP_EXPIRED = "safety_cap_expired"


class SubscriptionSimulationRequest(BaseModel):
    scenario: SubscriptionSimulationScenario
    academic_term_id: uuid.UUID | None = None
    plan_code: SubscriptionPlan = SubscriptionPlan.PLUS


class SubscriptionSimulationState(BaseModel):
    tenant_id: uuid.UUID
    academic_term_id: uuid.UUID | None = None
    term_status: str | None = None
    entitlement_id: uuid.UUID | None = None
    plan_code: str
    status: str
    activated_at: datetime | None = None
    closed_at: datetime | None = None
    expired_at: datetime | None = None
    safety_expires_at: datetime | None = None
    payment_reference: str | None = None
    payment_status: str | None = None


class SubscriptionSimulationResponse(BaseModel):
    scenario: str
    detail: str
    state: SubscriptionSimulationState


class SubscriptionReconcileResponse(BaseModel):
    detail: str
    lifecycle: dict[str, int]
    plan_changes: dict[str, int] = Field(default_factory=dict)
    state: SubscriptionSimulationState
