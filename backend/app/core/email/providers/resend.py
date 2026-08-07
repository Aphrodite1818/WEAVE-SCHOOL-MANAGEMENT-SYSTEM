"""Production-only Resend email delivery provider."""

from __future__ import annotations

import email.utils
import re
from typing import Any

import resend
from pydantic import SecretStr

from app.config.logging import get_logger
from app.config.settings import EnvironmentType, Settings, settings
from app.core.email.contracts import EmailDeliveryResult, EmailRequest, EmailRoute
from app.core.email.enums import EmailProvider
from app.core.email.exceptions import EmailConfigurationError, EmailProviderError
from app.core.email.providers.base import EmailProviderAdapter
from app.core.email.routing import resolve_email_route


logger = get_logger(__name__)
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})


class ResendEmailProvider(EmailProviderAdapter):
    """Deliver transactional, security, and bulk mail through Resend."""

    def __init__(self, *, config: Settings = settings) -> None:
        self._config = config
        if self._config.ENV != EnvironmentType.PRODUCTION:
            raise EmailConfigurationError("Resend email delivery is allowed only in production.")

    @property
    def provider(self) -> EmailProvider:
        return EmailProvider.RESEND

    @staticmethod
    def _secret_text(value: SecretStr | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        normalized = str(value).strip()
        return normalized or None

    def _api_key(self) -> str:
        api_key = self._secret_text(self._config.RESEND_API_KEY)
        if api_key is None:
            raise EmailConfigurationError("RESEND_API_KEY must be configured in production.")
        return api_key

    @staticmethod
    def _format_sender(route: EmailRoute) -> str:
        if not route.sender_name.strip():
            return route.sender_email.strip()
        return email.utils.formataddr((route.sender_name.strip(), route.sender_email.strip()))

    @staticmethod
    def _html_to_plain_text(html: str) -> str:
        plain_text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", plain_text).strip()

    @classmethod
    def _build_payload(cls, *, request: EmailRequest, route: EmailRoute) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": cls._format_sender(route),
            "to": [request.to_email.strip()],
            "subject": request.subject.strip(),
        }
        if request.is_html:
            payload["html"] = request.body
            payload["text"] = cls._html_to_plain_text(request.body)
        else:
            payload["text"] = request.body

        reply_to = cls._secret_text(request.reply_to or route.reply_to)
        if reply_to is not None:
            payload["reply_to"] = reply_to
        if request.tags:
            payload["tags"] = [
                {"name": name.strip(), "value": value.strip()} for name, value in request.tags
            ]
        return payload

    @staticmethod
    def _error_details(error: Exception) -> tuple[str, int | None, bool]:
        raw_code = getattr(error, "code", None)
        code = str(raw_code or error.__class__.__name__)
        raw_status = getattr(error, "status_code", None)
        status_code = raw_status if isinstance(raw_status, int) else None
        retryable = bool(
            status_code in _RETRYABLE_STATUS_CODES
            or (status_code is not None and status_code >= 500)
            or code.lower() in {"rate_limit_exceeded", "internal_server_error", "timeout"}
        )
        return code, status_code, retryable

    async def send(self, *, request: EmailRequest) -> EmailDeliveryResult:
        route = resolve_email_route(
            request.category,
            provider=EmailProvider.RESEND,
            config=self._config,
        )
        payload = self._build_payload(request=request, route=route)

        resend.api_key = self._api_key()
        try:
            response = await resend.Emails.send_async(payload)
        except Exception as exc:
            code, status_code, retryable = self._error_details(exc)
            logger.warning(
                "Resend rejected email in category %s with code %s and status %s.",
                request.category.value,
                code,
                status_code,
            )
            raise EmailProviderError(
                "Resend failed to accept the email.",
                provider=self.provider,
                code=code,
                retryable=retryable,
            ) from exc

        message_id = getattr(response, "id", None)
        if message_id is None and isinstance(response, dict):
            message_id = response.get("id")
        if not isinstance(message_id, str) or not message_id.strip():
            raise EmailProviderError(
                "Resend accepted the request without returning a valid email id.",
                provider=self.provider,
                code="missing_message_id",
                retryable=False,
            )

        logger.info(
            "Resend accepted email %s in category %s.",
            message_id,
            request.category.value,
        )
        return EmailDeliveryResult(
            provider=self.provider,
            accepted=True,
            message_id=message_id.strip(),
        )
