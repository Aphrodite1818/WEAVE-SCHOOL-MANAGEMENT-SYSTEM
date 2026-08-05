"""Legacy Google Apps Script and SMTP email provider
    Mainly targeted for local development and testing, but not in production environment.
"""

from __future__ import annotations

import email.utils
import re
from typing import Literal

import aiosmtplib
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pydantic import SecretStr


from app.config.logging import get_logger
from app.config.settings import Settings, settings
from app.core.email.contracts import (
    EmailDeliveryResult,
    EmailRequest,
    EmailRoute,
)
from app.core.email.enums import EmailProvider
from app.core.email.exceptions import (
    EmailConfigurationError,
    EmailProviderError,
)

from app.core.email.providers.base import EmailProviderAdapter


logger = get_logger(__name__)


class LegacyEmailProvider(EmailProviderAdapter):
    """Deliver email through Apps Script with SMTP as a fallback

    This adapter preserves the current legacy delivery order:

    1. Try Google Apps Script (GAS) first, if configured.
    2. Fall back to SMTP if GAS fails or is not configured, fails with an exception or returns a non-200 status code.
    3. A successful HTTP response explicitly containing
       "{"status": "false"}" is treated as a provider rejection and
       falls back to SMTP, matching the current sender logic
    """

    def __init__(self, *, config: Settings = settings) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_value(value: object) -> bool:
        if value is None:
            return False

        if isinstance(value, SecretStr):
            value = value.get_secret_value()

        return bool(str(value).strip())

    @staticmethod
    def _html_to_plain_text(html: str) -> str:
        """Produce a simple plain-text fallback from HTML"""

        plain_text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", plain_text).strip()

    @staticmethod
    def _secret_value(
        value: SecretStr | str | None
    ) -> None | str:
        """Return the raw value from a normal or secret setting"""

        if value is None:
            return None

        if isinstance(value, SecretStr):
            return value.get_secret_value()

        return value

    def _smtp_is_configured(self) -> bool:
        """Return whether the complete SMTP fallback is configured"""

        return all(
            [
                self._has_value(self._config.SMTP_HOST),
                self._has_value(self._config.SMTP_FROM_EMAIL),
                self._has_value(
                    self._secret_value(
                        self._config.SMTP_PASSWORD
                    )
                ),
            ]
        )

    def _build_smtp_message(
        self,
        *,
        request: EmailRequest,
        route: EmailRoute,
        from_email: str,
    ) -> MIMEMultipart:
        """Build the MIME message used by the SMTP transport"""

        message = (
            MIMEMultipart("alternative")
            if request.is_html
            else MIMEMultipart()
        )

        message["From"] = from_email
        message["To"] = request.to_email
        message["Subject"] = request.subject
        message["Date"] = email.utils.formatdate(localtime=True)

        sender_domain = from_email.split("@")[-1]

        message["Message-ID"] = email.utils.make_msgid(
            domain=sender_domain
        )

        reply_to = request.reply_to or route.reply_to

        if self._has_value(reply_to):
            message["Reply-To"] = reply_to.strip()

        if request.is_html:
            plain_text = self._html_to_plain_text(request.body)

            message.attach(
                MIMEText(
                    plain_text,
                    "plain",
                    "utf-8",
                )
            )
            message.attach(
                MIMEText(
                    request.body,
                    "html",
                    "utf-8",
                )
            )

        else:
            message.attach(
                MIMEText(
                    request.body,
                    "plain",
                    "utf-8",
                )
            )

        return message

    async def _send_with_app_script(
        self,
        *,
        request: EmailRequest,
    ) -> bool:
        """Attempt delivery through the configured Apps Script endpoint."""

        app_script_url = self._config.APP_SCRIPT_URL

        if not self._has_value(app_script_url):
            return False

        assert app_script_url is not None

        payload = {
            "to": request.to_email,
            "subject": request.subject,
            "body": request.body,
            "html": request.body if request.is_html else None,
        }

        timeout = httpx.Timeout(
            timeout=12.0,
            connect=5.0,
        )

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    app_script_url,
                    json=payload,
                )

            if response.status_code != 200:
                logger.warning(
                    "Apps Script email delivery returned status %s "
                    "for recipient %s.",
                    response.status_code,
                    request.to_email,
                )
                return False

            try:
                response_payload = response.json()
            except ValueError:
                logger.warning(
                    "Apps Script returned an invalid JSON response "
                    "for recipient %s.",
                    request.to_email,
                )
                return False

            if (
                isinstance(response_payload, dict)
                and response_payload.get("success") is False
            ):
                logger.warning(
                    "Apps Script rejected email delivery for recipient %s.",
                    request.to_email,
                )
                return False

            logger.info(
                "Email accepted by Apps Script for recipient %s.",
                request.to_email,
            )
            return True

        except httpx.HTTPError:
            logger.exception(
                "Apps Script request failed for recipient %s.",
                request.to_email,
            )
            return False

    async def _send_with_smtp(
        self,
        *,
        request: EmailRequest,
        route: EmailRoute,
    ) -> None:
        """Deliver one message through the configured SMTP server"""

        smtp_host = self._config.SMTP_HOST
        smtp_from_email = self._config.SMTP_FROM_EMAIL
        smtp_password = self._secret_value(
            self._config.SMTP_PASSWORD
        )

        if (
            not self._has_value(smtp_host)
            or not self._has_value(smtp_from_email)
            or not self._has_value(smtp_password)
        ):
            raise EmailConfigurationError(
                "SMTP requires SMTP_HOST, SMTP_FROM_EMAIL,"
                "and SMTP_PASSWORD"
            )

        message = self._build_smtp_message(
            request=request,
            route=route,
            from_email=smtp_from_email,
        )

        smtp = aiosmtplib.SMTP(
            hostname=smtp_host,
            port=self._config.SMTP_PORT,
            start_tls=self._config.SMTP_PORT == 587,
            use_tls=self._config.SMTP_PORT == 465,
            timeout=15,
        )

        try:
            await smtp.connect()

            await smtp.login(
                smtp_from_email,
                smtp_password,
            )

            await smtp.send_message(message)

            logger.info(
                "Email accepted by SMTP for recipient %s",
                request.to_email,
            )

        except Exception as exc:
            logger.exception(
                "SMTP email delivery failed for recipient %s",
                request.to_email,
            )

            raise EmailProviderError(
                "SMTP failed to deliver the email",
                provider=self.provider,
                code="smtp_delivery_failed",
                retryable=True,
            ) from exc

        finally:
            try:
                if smtp.is_connected:
                    await smtp.quit()

            except Exception:
                logger.warning(
                    "Failed to close SMTP connection cleanly",
                    exc_info=True,
                )

    @property
    def provider(self) -> EmailProvider:
        """Return the provider represented by this adapter"""

        return EmailProvider.LEGACY

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def send(
        self,
        *,
        request: EmailRequest,
        route: EmailRoute,
    ) -> EmailDeliveryResult | None:
        """Send one message using Apps Script or SMTP"""

        if self._has_value(self._config.APP_SCRIPT_URL):
            sent_with_app_script = await self._send_with_app_script(
                request=request
            )

            if sent_with_app_script:
                return EmailDeliveryResult(
                    provider=self.provider,
                    accepted=True,
                )

        if not self._smtp_is_configured():
            raise EmailConfigurationError(
                "Legacy email delivery failed through Apps Script and "
                "complete SMTP fallback settings are not configured"
            )

        await self._send_with_smtp(
            request=request,
            route=route,
        )

        return EmailDeliveryResult(
            provider=self.provider,
            accepted=True,
        )