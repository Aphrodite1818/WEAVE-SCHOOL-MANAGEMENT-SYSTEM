from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.config.settings import settings


class PaystackProviderError(Exception):
    """Raised when the Paystack provider call fails."""


class PaystackClient:
    """Thin async client for Paystack transaction and webhook operations."""

    def __init__(self) -> None:
        self.base_url = str(getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")).rstrip("/")
        self.secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", None)

    def _headers(self) -> dict[str, str]:
        if not self.secret_key:
            raise PaystackProviderError("PAYSTACK_SECRET_KEY is not configured.")

        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _normalize_plan_code(plan_code: str) -> str:
        normalized = str(plan_code or "").strip().strip('"').strip("'")
        if not normalized.startswith("PLN_"):
            raise PaystackProviderError(
                "Invalid Paystack plan code configured. Expected a plan code beginning with PLN_."
            )
        return normalized

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_kobo: int,
        reference: str,
        plan_code: str,
        callback_url: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "plan": self._normalize_plan_code(plan_code),
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

        if response.status_code >= 400:
            raise PaystackProviderError(f"Paystack initialize failed: {response.text}")

        parsed = response.json()
        if not parsed.get("status"):
            raise PaystackProviderError(str(parsed.get("message") or "Paystack initialize failed"))

        return parsed

    async def verify_transaction(
        self,
        *,
        reference: str,
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self._headers(),
            )

        if response.status_code >= 400:
            raise PaystackProviderError(f"Paystack verify failed: {response.text}")

        parsed = response.json()
        if not parsed.get("status"):
            raise PaystackProviderError(str(parsed.get("message") or "Paystack verify failed"))

        return parsed

    async def disable_subscription(
        self,
        *,
        code: str,
        token: str,
    ) -> dict[str, Any]:
        payload = {"code": code, "token": token}
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/subscription/disable",
                headers=self._headers(),
                json=payload,
            )

        if response.status_code >= 400:
            raise PaystackProviderError(f"Paystack subscription disable failed: {response.text}")

        parsed = response.json()
        if not parsed.get("status"):
            raise PaystackProviderError(
                str(parsed.get("message") or "Paystack subscription disable failed")
            )
        return parsed

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

    def parse_webhook_body(
        self,
        body: bytes,
    ) -> dict[str, Any]:
        return json.loads(body.decode("utf-8"))
