from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailProviderError
from app.core.email.providers.resend import ResendEmailProvider


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "EMAIL_SENDER_NAME": "WEAVE",
        "EMAIL_REPLY_TO": "support@weavecloudspace.com",
        "RESEND_API_KEY": SecretStr("re_test_key"),
        "RESEND_BASE_URL": "https://api.resend.com",
        "RESEND_TRANSACTIONAL_FROM_EMAIL": "no-reply@weavecloudspace.com",
        "RESEND_SECURITY_FROM_EMAIL": "security@weavecloudspace.com",
        "RESEND_BULK_FROM_EMAIL": "updates@weavecloudspace.com",
        "RESEND_TIMEOUT_SECONDS": 10.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_resend_provider_sends_html_email_with_category_sender_and_tags() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == httpx.URL("https://api.resend.com/emails")
        assert request.headers["authorization"] == "Bearer re_test_key"
        assert request.headers["user-agent"] == "weave-email/1.0"

        payload = json.loads(request.content.decode())
        assert payload == {
            "from": "WEAVE <updates@weavecloudspace.com>",
            "to": ["parent@example.com"],
            "subject": "Import complete",
            "html": "<p>Done</p>",
            "reply_to": "reply@example.com",
            "tags": [{"name": "email_type", "value": "parent_invitation"}],
        }

        return httpx.Response(
            200,
            json={"id": "email_123"},
            headers={"x-request-id": "req_123"},
        )

    provider = ResendEmailProvider(
        config=_config(),
        transport=httpx.MockTransport(handler),
    )

    result = await provider.send(
        request=EmailRequest(
            to_email="parent@example.com",
            subject="Import complete",
            body="<p>Done</p>",
            category=EmailCategory.BULK,
            is_html=True,
            reply_to="reply@example.com",
            tags=(("email_type", "parent_invitation"),),
        )
    )

    assert result.accepted is True
    assert result.provider == EmailProvider.RESEND
    assert result.message_id == "email_123"
    assert result.request_id == "req_123"


@pytest.mark.asyncio
async def test_resend_provider_uses_text_and_default_reply_to() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["from"] == "WEAVE <security@weavecloudspace.com>"
        assert payload["text"] == "Security alert"
        assert "html" not in payload
        assert payload["reply_to"] == "support@weavecloudspace.com"
        return httpx.Response(200, json={"id": "email_security"})

    provider = ResendEmailProvider(
        config=_config(),
        transport=httpx.MockTransport(handler),
    )

    result = await provider.send(
        request=EmailRequest(
            to_email="admin@example.com",
            subject="Security",
            body="Security alert",
            category=EmailCategory.SECURITY,
        )
    )

    assert result.message_id == "email_security"


@pytest.mark.asyncio
async def test_resend_provider_marks_rate_limit_as_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            429,
            json={
                "name": "rate_limit_exceeded",
                "message": "Too many requests.",
            },
        )

    provider = ResendEmailProvider(
        config=_config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmailProviderError) as exc_info:
        await provider.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )

    assert exc_info.value.provider == EmailProvider.RESEND
    assert exc_info.value.code == "rate_limit_exceeded"
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_resend_provider_marks_invalid_api_key_as_non_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            403,
            json={
                "name": "validation_error",
                "message": "API key is invalid.",
            },
        )

    provider = ResendEmailProvider(
        config=_config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmailProviderError) as exc_info:
        await provider.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_resend_provider_translates_transport_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    provider = ResendEmailProvider(
        config=_config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmailProviderError) as exc_info:
        await provider.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )

    assert exc_info.value.provider == EmailProvider.RESEND
    assert exc_info.value.retryable is True
