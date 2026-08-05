"""Amazon SES v2 email delivery provider."""

from __future__ import annotations

import asyncio
import email.utils
import re
from functools import cached_property
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
    PartialCredentialsError,
    ReadTimeoutError,
)
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
    EmailValidationError,
)
from app.core.email.providers.base import EmailProviderAdapter
from app.core.email.routing import resolve_email_route


logger = get_logger(__name__)


SES_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")

RETRYABLE_SES_ERROR_CODES = frozenset(
    {
        "TooManyRequestsException",
        "LimitExceededException",
        "Throttling",
        "ThrottlingException",
        "RequestTimeout",
        "RequestTimeoutException",
        "InternalFailure",
        "InternalServiceError",
        "InternalServiceErrorException",
        "ServiceUnavailable",
        "ServiceUnavailableException",
    }
)


class SESEmailProvider(EmailProviderAdapter):
    """Deliver email through the Amazon SES v2 API."""

    def __init__(self, *, config: Settings = settings) -> None:
        self._config = config

    @property
    def provider(self) -> EmailProvider:
        """Return the provider represented by this adapter."""

        return EmailProvider.SES

    # ==========================================================
    # SHARED SETTING HELPERS
    # ==========================================================

    @staticmethod
    def _setting_value(
        value: SecretStr | str | None,
    ) -> str | None:
        """Return a normalized normal or secret setting value."""

        if value is None:
            return None

        if isinstance(value, SecretStr):
            value = value.get_secret_value()

        cleaned_value = value.strip()

        return cleaned_value or None

    @classmethod
    def _require_setting(
        cls,
        value: SecretStr | str | None,
        *,
        setting_name: str,
    ) -> str:
        """Return a required setting or raise a configuration error."""

        normalized_value = cls._setting_value(value)

        if normalized_value is None:
            raise EmailConfigurationError(
                f"{setting_name} must be configured for Amazon SES."
            )

        return normalized_value

    @classmethod
    def _optional_setting(
        cls,
        value: SecretStr | str | None,
    ) -> str | None:
        """Return a normalized optional setting."""

        return cls._setting_value(value)

    # ==========================================================
    # CONTENT HELPERS
    # ==========================================================

    @staticmethod
    def _html_to_plain_text(html: str) -> str:
        """Produce a basic plain-text fallback from HTML content."""

        plain_text = re.sub(r"<[^>]+>", " ", html)

        return re.sub(r"\s+", " ", plain_text).strip()

    @staticmethod
    def _format_sender(route: EmailRoute) -> str:
        """Build the friendly From address accepted by Amazon SES."""

        sender_email = route.sender_email.strip()
        sender_name = route.sender_name.strip()

        if not sender_name:
            return sender_email

        return email.utils.formataddr(
            (sender_name, sender_email),
            charset="utf-8",
        )

    @classmethod
    def _resolve_reply_to(
        cls,
        *,
        request: EmailRequest,
        route: EmailRoute,
    ) -> str | None:
        """Resolve request-specific or default reply-to configuration."""

        return cls._optional_setting(
            request.reply_to or route.reply_to,
        )

    # ==========================================================
    # SES MESSAGE TAGS
    # ==========================================================

    @staticmethod
    def _validate_tag_component(
        value: str,
        *,
        component_name: str,
    ) -> str:
        """Validate and normalize an SES message-tag component."""

        normalized_value = value.strip()

        if not SES_TAG_PATTERN.fullmatch(normalized_value):
            raise EmailValidationError(
                f"SES email tag {component_name} '{normalized_value}' "
                "must contain only ASCII letters, numbers, hyphens, "
                "or underscores and must not exceed 256 characters."
            )

        return normalized_value

    @classmethod
    def _build_email_tags(
        cls,
        request: EmailRequest,
    ) -> list[dict[str, str]]:
        """Convert request tags to the Amazon SES message-tag format."""

        email_tags: list[dict[str, str]] = []

        for name, value in request.tags:
            normalized_name = cls._validate_tag_component(
                name,
                component_name="name",
            )
            normalized_value = cls._validate_tag_component(
                value,
                component_name="value",
            )

            email_tags.append(
                {
                    "Name": normalized_name,
                    "Value": normalized_value,
                }
            )

        return email_tags

    # ==========================================================
    # SES CONTENT CONSTRUCTION
    # ==========================================================

    @classmethod
    def _build_simple_content(
        cls,
        request: EmailRequest,
    ) -> dict[str, Any]:
        """Build SES Simple email content from the request."""

        body: dict[str, dict[str, str]]

        if request.is_html:
            body = {
                "Text": {
                    "Data": cls._html_to_plain_text(request.body),
                    "Charset": "UTF-8",
                },
                "Html": {
                    "Data": request.body,
                    "Charset": "UTF-8",
                },
            }

        else:
            body = {
                "Text": {
                    "Data": request.body,
                    "Charset": "UTF-8",
                }
            }

        return {
            "Subject": {
                "Data": request.subject.strip(),
                "Charset": "UTF-8",
            },
            "Body": body,
        }

    @classmethod
    def _build_send_payload(
        cls,
        *,
        request: EmailRequest,
        route: EmailRoute,
    ) -> dict[str, Any]:
        """Build the complete SES v2 SendEmail request payload."""

        payload: dict[str, Any] = {
            "FromEmailAddress": cls._format_sender(route),
            "Destination": {
                "ToAddresses": [
                    request.to_email.strip(),
                ]
            },
            "Content": {
                "Simple": cls._build_simple_content(request),
            },
            "ConfigurationSetName": route.configuration_set.strip(),
        }

        reply_to = cls._resolve_reply_to(
            request=request,
            route=route,
        )

        if reply_to is not None:
            payload["ReplyToAddresses"] = [reply_to]

        email_tags = cls._build_email_tags(request)

        if email_tags:
            payload["EmailTags"] = email_tags

        return payload

    # ==========================================================
    # SES CLIENT CONSTRUCTION
    # ==========================================================

    def _create_client(self) -> Any:
        """Create the configured synchronous Amazon SES v2 client."""

        aws_region = self._require_setting(
            self._config.AWS_REGION,
            setting_name="AWS_REGION",
        )
        aws_access_key_id = self._require_setting(
            self._config.AWS_ACCESS_KEY_ID,
            setting_name="AWS_ACCESS_KEY_ID",
        )
        aws_secret_access_key = self._require_setting(
            self._config.AWS_SECRET_ACCESS_KEY,
            setting_name="AWS_SECRET_ACCESS_KEY",
        )

        aws_session_token = self._optional_setting(
            self._config.AWS_SESSION_TOKEN,
        )
        endpoint_url = self._optional_setting(
            self._config.AWS_SES_ENDPOINT_URL,
        )

        client_options: dict[str, Any] = {
            "service_name": "sesv2",
            "region_name": aws_region,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "config": Config(
                connect_timeout=(
                    self._config.SES_CONNECT_TIMEOUT_SECONDS
                ),
                read_timeout=(
                    self._config.SES_READ_TIMEOUT_SECONDS
                ),
                retries={
                    "total_max_attempts": (
                        self._config.SES_MAX_ATTEMPTS
                    ),
                    "mode": "standard",
                },
            ),
        }

        if aws_session_token is not None:
            client_options["aws_session_token"] = aws_session_token

        if endpoint_url is not None:
            client_options["endpoint_url"] = endpoint_url

        return boto3.client(**client_options)

    @cached_property
    def _client(self) -> Any:
        """Create and cache one SES client for this provider instance."""

        return self._create_client()

    # ==========================================================
    # AWS ERROR TRANSLATION
    # ==========================================================

    @staticmethod
    def _extract_client_error_details(
        error: ClientError,
    ) -> tuple[str, str, int | None]:
        """Extract the normalized AWS error code, message, and status."""

        error_response = error.response.get("Error", {})
        response_metadata = error.response.get("ResponseMetadata", {})

        error_code = str(
            error_response.get("Code", "unknown_ses_error")
        )
        error_message = str(
            error_response.get(
                "Message",
                "Amazon SES rejected the email request.",
            )
        )

        status_value = response_metadata.get("HTTPStatusCode")
        status_code = (
            status_value
            if isinstance(status_value, int)
            else None
        )

        return error_code, error_message, status_code

    @staticmethod
    def _is_retryable_client_error(
        *,
        error_code: str,
        status_code: int | None,
    ) -> bool:
        """Return whether a final SES client error may be retried."""

        if error_code in RETRYABLE_SES_ERROR_CODES:
            return True

        return bool(
            status_code is not None
            and status_code >= 500
        )

    @classmethod
    def _translate_client_error(
        cls,
        error: ClientError,
    ) -> EmailProviderError:
        """Convert an AWS service response into an email provider error."""

        error_code, error_message, status_code = (
            cls._extract_client_error_details(error)
        )

        retryable = cls._is_retryable_client_error(
            error_code=error_code,
            status_code=status_code,
        )

        return EmailProviderError(
            f"Amazon SES failed to accept the email: {error_message}",
            provider=EmailProvider.SES,
            code=error_code,
            retryable=retryable,
        )

    @staticmethod
    def _translate_transport_error(
        error: BotoCoreError,
    ) -> EmailProviderError:
        """Convert an AWS SDK transport error into a provider error."""

        return EmailProviderError(
            "Amazon SES could not be reached.",
            provider=EmailProvider.SES,
            code=error.__class__.__name__,
            retryable=True,
        )

    # ==========================================================
    # SYNCHRONOUS SDK EXECUTION
    # ==========================================================

    def _send_sync(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the synchronous Boto3 SendEmail operation."""

        return self._client.send_email(**payload)

    # ==========================================================
    # RESPONSE PROCESSING
    # ==========================================================

    @staticmethod
    def _extract_message_id(
        response: dict[str, Any],
    ) -> str:
        """Extract the required SES message identifier."""

        message_id = response.get("MessageId")

        if not isinstance(message_id, str) or not message_id.strip():
            raise EmailProviderError(
                "Amazon SES accepted the request without returning "
                "a valid MessageId.",
                provider=EmailProvider.SES,
                code="missing_message_id",
                retryable=False,
            )

        return message_id.strip()

    @staticmethod
    def _extract_request_id(
        response: dict[str, Any],
    ) -> str | None:
        """Extract the optional AWS request identifier."""

        response_metadata = response.get("ResponseMetadata")

        if not isinstance(response_metadata, dict):
            return None

        request_id = response_metadata.get("RequestId")

        if not isinstance(request_id, str):
            return None

        normalized_request_id = request_id.strip()

        return normalized_request_id or None

    # ==========================================================
    # PUBLIC ENTRY POINT
    # ==========================================================

    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        """Send one email through Amazon SES v2."""

        route = resolve_email_route(
            request.category,
            config=self._config,
        )

        payload = self._build_send_payload(
            request=request,
            route=route,
        )

        try:
            response = await asyncio.to_thread(
                self._send_sync,
                payload,
            )

        except (
            NoCredentialsError,
            PartialCredentialsError,
            NoRegionError,
        ) as exc:
            raise EmailConfigurationError(
                "Amazon SES credentials or region configuration "
                "could not be resolved."
            ) from exc

        except ClientError as exc:
            translated_error = self._translate_client_error(exc)

            logger.warning(
                "Amazon SES rejected an email in category %s "
                "with error code %s.",
                request.category.value,
                translated_error.code,
            )

            raise translated_error from exc

        except (
            EndpointConnectionError,
            ConnectionClosedError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as exc:
            translated_error = self._translate_transport_error(exc)

            logger.exception(
                "Amazon SES transport failure for category %s.",
                request.category.value,
            )

            raise translated_error from exc

        except BotoCoreError as exc:
            logger.exception(
                "Unexpected Amazon SES SDK failure for category %s.",
                request.category.value,
            )

            raise EmailProviderError(
                "Amazon SES SDK failed while processing the email.",
                provider=self.provider,
                code=exc.__class__.__name__,
                retryable=False,
            ) from exc

        message_id = self._extract_message_id(response)
        request_id = self._extract_request_id(response)

        logger.info(
            "Amazon SES accepted email %s in category %s.",
            message_id,
            request.category.value,
        )

        return EmailDeliveryResult(
            provider=self.provider,
            accepted=True,
            message_id=message_id,
            request_id=request_id,
        )