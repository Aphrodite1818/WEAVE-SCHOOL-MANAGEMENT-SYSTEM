from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.config.settings import EnvironmentType
from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailConfigurationError, EmailProviderError
from app.core.email.providers.resend import ResendEmailProvider


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "ENV": EnvironmentType.PRODUCTION,
        "RESEND_API_KEY": SecretStr("re_test_key"),
        "RESEND_TRANSACTIONAL_FROM_EMAIL": "no-reply@notifications.weavecloudspace.com",
        "RESEND_SECURITY_FROM_EMAIL": "security@notifications.weavecloudspace.com",
        "RESEND_BULK_FROM_EMAIL": "updates@updates.weavecloudspace.com",
        "EMAIL_SENDER_NAME": "WEAVE",
        "EMAIL_REPLY_TO": "support@weavecloudspace.com",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resend_provider_cannot_initialize_outside_production() -> None:
    with pytest.raises(EmailConfigurationError, match="only in production"):
        ResendEmailProvider(config=_config(ENV=EnvironmentType.STAGING))


@pytest.mark.asyncio
async def test_resend_provider_sends_category_route(monkeypatch: pytest.MonkeyPatch) -> None:
    send_async = AsyncMock(return_value={"id": "email_123"})
    monkeypatch.setattr("app.core.email.providers.resend.resend.Emails.send_async", send_async)
    provider = ResendEmailProvider(config=_config())

    result = await provider.send(
        request=EmailRequest(
            to_email="user@example.com",
            subject="Security alert",
            body="<strong>Alert</strong>",
            category=EmailCategory.SECURITY,
            is_html=True,
            tags=(("category", "security"),),
        )
    )

    assert result.provider == EmailProvider.RESEND
    assert result.message_id == "email_123"
    payload = send_async.await_args.args[0]
    assert payload["from"] == "WEAVE <security@notifications.weavecloudspace.com>"
    assert payload["to"] == ["user@example.com"]
    assert payload["reply_to"] == "support@weavecloudspace.com"
    assert payload["html"] == "<strong>Alert</strong>"
    assert payload["text"] == "Alert"
    assert payload["tags"] == [{"name": "category", "value": "security"}]


@pytest.mark.asyncio
async def test_resend_provider_translates_retryable_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RateLimitError(Exception):
        code = "rate_limit_exceeded"
        status_code = 429

    monkeypatch.setattr(
        "app.core.email.providers.resend.resend.Emails.send_async",
        AsyncMock(side_effect=RateLimitError("limited")),
    )
    provider = ResendEmailProvider(config=_config())

    with pytest.raises(EmailProviderError) as error_info:
        await provider.send(
            request=EmailRequest(to_email="user@example.com", subject="Subject", body="Body")
        )

    assert error_info.value.provider == EmailProvider.RESEND
    assert error_info.value.code == "rate_limit_exceeded"
    assert error_info.value.retryable is True


@pytest.mark.asyncio
async def test_resend_provider_requires_api_key_at_send_time() -> None:
    provider = ResendEmailProvider(config=_config(RESEND_API_KEY=None))
    with pytest.raises(EmailConfigurationError, match="RESEND_API_KEY"):
        await provider.send(
            request=EmailRequest(to_email="user@example.com", subject="Subject", body="Body")
        )
