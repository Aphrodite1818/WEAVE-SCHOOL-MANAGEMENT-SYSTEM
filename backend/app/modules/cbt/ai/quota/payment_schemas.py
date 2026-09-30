from __future__ import annotations

from pydantic import Field

from app.modules.cbt.ai.quota.schemas import AIQuotaPurchaseResponse, AIQuotaSchemaBase


class AIQuotaPurchaseQuote(AIQuotaSchemaBase):
    credits: int = Field(gt=0)
    unit_price_kobo: int = Field(gt=0)
    amount_kobo: int = Field(gt=0)
    currency: str = "NGN"


class AIQuotaPurchaseCheckoutResponse(AIQuotaSchemaBase):
    purchase: AIQuotaPurchaseResponse
    quote: AIQuotaPurchaseQuote
    authorization_url: str
    access_code: str
