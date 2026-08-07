from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import SecretStr

from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailProviderError, EmailValidationError
from app.core.email.providers.ses import SESEmailProvider
from app.core.email.routing import resolve_email_route


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "AWS_REGION": "eu-west-1",
        "AWS_ACCESS_KEY_ID": "access-key",
        "AWS_SECRET_ACCESS_KEY": SecretStr("secret-key"),
        "AWS_SESSION_TOKEN": None,
        "AWS_SES_ENDPOINT_URL": None,
        "SES_CONNECT_TIMEOUT_SECONDS": 5,
        "SES_READ_TIMEOUT_SECONDS": 10,
        "SES_MAX_ATTEMPTS": 3,
        "EMAIL_SENDER_NAME": "WEAVE",
        "EMAIL_REPLY_TO": "support@weavecloudspace.com",
        "SES_TRANSACTIONAL_FROM_EMAIL": "no-reply@notifications.weavecloudspace.com",
        "SES_SECURITY_FROM_EMAIL": "security@notifications.weavecloudspace.com",
        "SES_BULK_FROM_EMAIL": "updates@updates.weavecloudspace.com",
        "SES_TRANSACTIONAL_CONFIGURATION_SET": "weave-transactional",
        "SES_SECURITY_CONFIGURATION_SET": "weave-security",
        "SES_BULK_CONFIGURATION_SET": "weave-bulk",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_ses_payload_contains_route_content_reply_to_and_tags() -> None:
    config = _config()
    request = EmailRequest(
        to_email="user@example.com",
        subject="Security notice",
        body="<p>Review your account</p>",
        category=EmailCategory.SECURITY,
        is_html=True,
        tags=(("email_type", "security_alert"),),
    )
    route = resolve_email_route(request.category, config=config)

    payload = SESEmailProvider._build_send_payload(
        request=request,
        route=route,
    )

    assert payload["FromEmailAddress"] == (
        "WEAVE <security@notifications.weavecloudspace.com>"
    )
    assert payload["Destination"] == {"ToAddresses": ["user@example.com"]}
    assert payload["ConfigurationSetName"] == "weave-security"
    assert payload["ReplyToAddresses"] == ["support@weavecloudspace.com"]
    assert payload["EmailTags"] == [{"Name": "email_type", "Value": "security_alert"}]
    assert payload["Content"]["Simple"]["Body"]["Html"]["Data"] == request.body
    assert payload["Content"]["Simple"]["Body"]["Text"]["Data"] == (
        "Review your account"
    )


def test_ses_payload_rejects_invalid_tag_characters() -> None:
    request = EmailRequest(
        to_email="user@example.com",
        subject="Subject",
        body="Body",
        tags=(("email type", "invalid value"),),
    )
    route = resolve_email_route(request.category, config=_config())

    with pytest.raises(EmailValidationError):
        SESEmailProvider._build_send_payload(
            request=request,
            route=route,
        )


@pytest.mark.asyncio
async def test_ses_send_returns_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SESEmailProvider(config=_config())
    captured: dict[str, Any] = {}

    def fake_send_sync(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "MessageId": "ses-message-id",
            "ResponseMetadata": {"RequestId": "aws-request-id"},
        }

    monkeypatch.setattr(provider, "_send_sync", fake_send_sync)

    result = await provider.send(
        request=EmailRequest(
            to_email="user@example.com",
            subject="Welcome",
            body="Hello",
        )
    )

    assert result.accepted is True
    assert result.provider == EmailProvider.SES
    assert result.message_id == "ses-message-id"
    assert result.request_id == "aws-request-id"
    assert captured["ConfigurationSetName"] == "weave-transactional"


@pytest.mark.asyncio
async def test_ses_client_error_is_translated_with_retryability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SESEmailProvider(config=_config())

    def fail_send_sync(_: dict[str, Any]) -> dict[str, Any]:
        raise ClientError(
            {
                "Error": {
                    "Code": "TooManyRequestsException",
                    "Message": "Rate exceeded",
                },
                "ResponseMetadata": {
                    "HTTPStatusCode": 429,
                    "RequestId": "request-id",
                },
            },
            "SendEmail",
        )

    monkeypatch.setattr(provider, "_send_sync", fail_send_sync)

    with pytest.raises(EmailProviderError) as error_info:
        await provider.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )

    assert error_info.value.provider == EmailProvider.SES
    assert error_info.value.code == "TooManyRequestsException"
    assert error_info.value.retryable is True


@pytest.mark.asyncio
async def test_ses_missing_message_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SESEmailProvider(config=_config())
    monkeypatch.setattr(provider, "_send_sync", lambda _: {})

    with pytest.raises(EmailProviderError) as error_info:
        await provider.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )

    assert error_info.value.code == "missing_message_id"
