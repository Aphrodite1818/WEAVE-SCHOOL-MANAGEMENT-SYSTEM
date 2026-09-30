from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.enums import PaymentProvider


class PaymentSchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaymentCheckoutSession(PaymentSchemaBase):
    reference: str
    authorization_url: str
    access_code: str


class VerifiedPayment(PaymentSchemaBase):
    reference: str
    amount_kobo: int = Field(gt=0)
    currency: str
    provider_transaction_id: str | None = None
    metadata: dict[str, Any]
    raw_payload: dict[str, Any]


class WebhookProcessingResponse(PaymentSchemaBase):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    success: bool
    provider: PaymentProvider
    event_type: str
    event_key: str
    duplicate: bool = False
    message: str
