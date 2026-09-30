from __future__ import annotations

from fastapi import APIRouter, Header, Request

from app.core.dependencies.db import DbSession
from app.modules.payments.dispatcher import settle_paystack_charge
from app.modules.payments.schemas import WebhookProcessingResponse
from app.modules.payments.webhook import process_paystack_webhook_secure

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/paystack/webhook", response_model=WebhookProcessingResponse)
async def process_paystack_webhook(
    request: Request,
    db: DbSession,
    x_paystack_signature: str | None = Header(default=None),
) -> WebhookProcessingResponse:
    """Shared Paystack webhook entrypoint for all Weave payment purposes."""

    body = await request.body()
    return await process_paystack_webhook_secure(
        db,
        body=body,
        signature=x_paystack_signature,
        settle_charge=settle_paystack_charge,
    )
