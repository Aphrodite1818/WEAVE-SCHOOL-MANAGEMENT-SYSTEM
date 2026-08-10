from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SubscriptionSimulationScenario(str, Enum):
    EXPIRES_IN_DAYS = "expires_in_days"
    PERIOD_ENDED = "period_ended"
    GRACE_EXPIRES_IN_DAYS = "grace_expires_in_days"
    GRACE_EXPIRED = "grace_expired"


class SubscriptionSimulationRequest(BaseModel):
    scenario: SubscriptionSimulationScenario
    days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def validate_adjustments(self) -> "SubscriptionSimulationRequest":
        if self.scenario in {
            SubscriptionSimulationScenario.EXPIRES_IN_DAYS,
            SubscriptionSimulationScenario.GRACE_EXPIRES_IN_DAYS,
        } and self.days is None:
            raise ValueError("days is required for this simulation scenario")
        return self


class SubscriptionSimulationState(BaseModel):
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID
    plan_code: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    grace_ends_at: datetime | None = None
    cancel_at_period_end: bool
    next_payment_at: datetime | None = None
    snapshot_available: bool = False


class SubscriptionSimulationResponse(BaseModel):
    scenario: str
    detail: str
    state: SubscriptionSimulationState


class SubscriptionReconcileResponse(BaseModel):
    detail: str
    lifecycle: dict[str, int]
    state: SubscriptionSimulationState
