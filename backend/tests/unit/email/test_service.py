from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.email.contracts import EmailDeliveryResult, EmailRequest
from app.core.email.enums import EmailProvider
from app.core.email.exceptions import EmailConfigurationError
from app.core.email.service import EmailService


class _FakeProvider:
    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider
        self.requests: list[EmailRequest] = []

    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        self.requests.append(request)
        return EmailDeliveryResult(
            provider=self.provider,
            accepted=True,
            message_id="message-1",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_type",
    [EmailProvider.LEGACY, EmailProvider.SES],
)
async def test_email_service_selects_configured_provider(
    provider_type: EmailProvider,
) -> None:
    provider = _FakeProvider(provider_type)
    service = EmailService(
        config=SimpleNamespace(EMAIL_PROVIDER=provider_type.value),
        providers={provider_type: provider},
    )
    request = EmailRequest(
        to_email="user@example.com",
        subject="Subject",
        body="Body",
    )

    result = await service.send(request=request)

    assert result.accepted is True
    assert result.provider == provider_type
    assert provider.requests == [request]


@pytest.mark.asyncio
async def test_email_service_rejects_unknown_provider() -> None:
    service = EmailService(
        config=SimpleNamespace(EMAIL_PROVIDER="unknown"),
    )

    with pytest.raises(EmailConfigurationError):
        await service.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )


@pytest.mark.asyncio
async def test_email_service_rejects_mismatched_provider_registry() -> None:
    service = EmailService(
        config=SimpleNamespace(EMAIL_PROVIDER=EmailProvider.SES.value),
        providers={
            EmailProvider.SES: _FakeProvider(EmailProvider.LEGACY),
        },
    )

    with pytest.raises(EmailConfigurationError):
        await service.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )
