from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config.settings import settings


class PaystackProviderError(Exception):
    """Raised when a Paystack provider operation fails."""


class PaystackClient:
    """Thin async Paystack client for one-time payments and webhooks."""

    def __init__(self) -> None:
        self.base_url = str(
            getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
        ).rstrip("/")
        self.secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", None)

    def _headers(self) -> dict[str, str]:
        if not self.secret_key:
            raise PaystackProviderError("PAYSTACK_SECRET_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _parse_response(response: httpx.Response, operation: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise PaystackProviderError(f"Paystack {operation} failed: {response.text}")
        parsed = response.json()
        if not parsed.get("status"):
            raise PaystackProviderError(
                str(parsed.get("message") or f"Paystack {operation} failed")
            )
        return parsed

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_kobo: int,
        reference: str,
        callback_url: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata,
        }
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/transaction/initialize",
                headers=self._headers(),
                json=payload,
            )
        return self._parse_response(response, "initialize")

    async def verify_transaction(self, *, reference: str) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.base_url}/transaction/verify/{quote(reference, safe='')}",
                headers=self._headers(),
            )
        return self._parse_response(response, "verify")

    def verify_webhook_signature(
        self,
        *,
        body: bytes,
        signature: str | None,
    ) -> bool:
        if not signature or not self.secret_key:
            return False
        digest = hmac.new(
            self.secret_key.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(digest, signature)

    @staticmethod
    def parse_webhook_body(body: bytes) -> dict[str, Any]:
        return json.loads(body.decode("utf-8"))
