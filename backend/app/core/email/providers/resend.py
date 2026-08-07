"""Resend email delivery provider."""

from __future__ import annotations

import email.utils
import re
from typing import Any

import httpx
from pydantic import SecretStr

from app.config.logging import get_logger
from app.config.settings import Settings, settings
from app.core.email.contracts import EmailDeliveryResult, EmailRequest
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import (
    EmailConfigurationError,
    EmailProviderError,
    EmailValidationError,
)
from app.core.email.providers.base import EmailProviderAdapter

logger = get_logger(__name__)

RESEND_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class ResendEmailProvider(EmailProviderAdapter):
    """Deliver email through the Resend REST API."""

    def __init__(
        self,
        *,
        config: Settings = settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    @property
    def provider(self) -> EmailProvider:
        """Return the provider represented by this adapter."""

        return EmailProvider.RESEND

    @staticmethod
    def _setting_value(value: SecretStr | str | None) -> str | None:
        """Return a normalized normal or secret setting value."""

        if value is None:
            return None

        if isinstance(value, SecretStr):
            value = value.get_secret_value()

        normalized = str(value).strip()
        return normalized or None

    @classmethod
    def _require_setting(
        cls,
        value: SecretStr | str | None,
        *,
        setting_name: str,
    ) -> str:
        """Return a required setting or raise a configuration error."""

        normalized = cls._setting_value(value)
        if normalized is None:
            raise EmailConfigurationError(f"{setting_name} must be configured for Resend.")
        return normalized

    def _resolve_sender_email(self, category: EmailCategory) -> str:
        """Resolve the configured sender for an email category."""

        if category == EmailCategory.TRANSACTIONAL:
            value = self._config.RESEND_TRANSACTIONAL_FROM_EMAIL
            setting_name = "RESEND_TRANSACTIONAL_FROM_EMAIL"
        elif category == EmailCategory.SECURITY:
            value = self._config.RESEND_SECURITY_FROM_EMAIL
            setting_name = "RESEND_SECURITY_FROM_EMAIL"
        elif category == EmailCategory.BULK:
            value = self._config.RESEND_BULK_FROM_EMAIL
            setting_name = "RESEND_BULK_FROM_EMAIL"
        else:
            raise EmailConfigurationError(f"Unsupported email category: {category!r}.")

        return self._require_setting(value, setting_name=setting_name)

    def _format_sender(self, category: EmailCategory) -> str:
        """Build the friendly From address accepted by Resend."""

        sender_email = self._resolve_sender_email(category)
        sender_name = self._setting_value(self._config.EMAIL_SENDER_NAME)

        if not sender_name:
            return sender_email

        return email.utils.formataddr((sender_name, sender_email), charset="utf-8")

    @staticmethod
    def _validate_tag_component(
        value: str,
        *,
        component_name: str,
    ) -> str:
        """Validate a Resend tag name or value."""

        normalized = value.strip()
        if not RESEND_TAG_PATTERN.fullmatch(normalized):
            raise EmailValidationError(
                f"Resend email tag {component_name} '{normalized}' must contain "
                "only ASCII letters, numbers, hyphens, or underscores and must "
                "not exceed 256 characters."
            )
        return normalized

    @classmethod
    def _build_tags(cls, request: EmailRequest) -> list[dict[str, str]]:
        """Convert provider-independent tags into the Resend format."""

        return [
            {
                "name": cls._validate_tag_component(name, component_name="name"),
                "value": cls._validate_tag_component(value, component_name="value"),
            }
            for name, value in request.tags
        ]

    def _build_payload(self, request: EmailRequest) -> dict[str, Any]:
        """Build the Resend send-email payload."""

        payload: dict[str, Any] = {
            "from": self._format_sender(request.category),
            "to": [request.to_email.strip()],
            "subject": request.subject.strip(),
        }

        if request.is_html:
            payload["html"] = request.body
        else:
            payload["text"] = request.body

        reply_to = self._setting_value(request.reply_to or self._config.EMAIL_REPLY_TO)
        if reply_to is not None:
            payload["reply_to"] = reply_to

        tags = self._build_tags(request)
        if tags:
            payload["tags"] = tags

        return payload

    def _build_headers(self) -> dict[str, str]:
        """Build authentication and required HTTP headers."""

        api_key = self._require_setting(
            self._config.RESEND_API_KEY,
            setting_name="RESEND_API_KEY",
        )
        return {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "weave-email/1.0",
        }

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        """Return whether a failed HTTP request is safe to retry later."""

        return status_code in {408, 429} or status_code >= 500

    @staticmethod
    def _error_details(response: httpx.Response) -> tuple[str, str]:
        """Extract a stable Resend error code and safe message."""

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        code = payload.get("name") or payload.get("code") or f"http_{response.status_code}"
        message = payload.get("message") or "Resend rejected the email request."

        return str(code), str(message)

    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        """Send one email through Resend."""

        base_url = self._require_setting(
            self._config.RESEND_BASE_URL,
            setting_name="RESEND_BASE_URL",
        ).rstrip("/")
        payload = self._build_payload(request)
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=self._config.RESEND_TIMEOUT_SECONDS,
                transport=self._transport,
                headers=headers,
            ) as client:
                response = await client.post("/emails", json=payload)
        except httpx.RequestError as exc:
            logger.exception(
                "Resend transport failure for category %s.",
                request.category.value,
            )
            raise EmailProviderError(
                "Resend could not be reached.",
                provider=self.provider,
                code=exc.__class__.__name__,
                retryable=True,
            ) from exc

        if not response.is_success:
            code, message = self._error_details(response)
            logger.warning(
                "Resend rejected an email in category %s with status %s and code %s.",
                request.category.value,
                response.status_code,
                code,
            )
            raise EmailProviderError(
                f"Resend failed to accept the email: {message}",
                provider=self.provider,
                code=code,
                retryable=self._is_retryable_status(response.status_code),
            )

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise EmailProviderError(
                "Resend accepted the request without returning valid JSON.",
                provider=self.provider,
                code="invalid_success_response",
                retryable=False,
            ) from exc

        message_id = response_payload.get("id") if isinstance(response_payload, dict) else None
        if not isinstance(message_id, str) or not message_id.strip():
            raise EmailProviderError(
                "Resend accepted the request without returning a valid email id.",
                provider=self.provider,
                code="missing_message_id",
                retryable=False,
            )

        request_id = response.headers.get("x-request-id") or response.headers.get("request-id")

        logger.info(
            "Resend accepted email %s in category %s.",
            message_id,
            request.category.value,
        )

        return EmailDeliveryResult(
            provider=self.provider,
            accepted=True,
            message_id=message_id.strip(),
            request_id=request_id.strip() if request_id else None,
        )
