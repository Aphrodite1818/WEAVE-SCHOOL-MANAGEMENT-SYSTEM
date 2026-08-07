from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config.settings import EnvironmentType
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


def _config(
    provider_type: EmailProvider | str,
    *,
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT,
) -> SimpleNamespace:
    value = provider_type.value if isinstance(provider_type, EmailProvider) else provider_type
    return SimpleNamespace(EMAIL_PROVIDER=value, ENV=environment)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_type",
    [EmailProvider.LEGACY, EmailProvider.SES],
)
async def test_non_production_email_service_selects_supported_provider(
    provider_type: EmailProvider,
) -> None:
    provider = _FakeProvider(provider_type)
    service = EmailService(
        config=_config(provider_type),
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
async def test_production_email_service_routes_through_resend() -> None:
    provider = _FakeProvider(EmailProvider.RESEND)
    service = EmailService(
        config=_config(
            EmailProvider.RESEND,
            environment=EnvironmentType.PRODUCTION,
        ),
        providers={EmailProvider.RESEND: provider},
    )
    request = EmailRequest(
        to_email="user@example.com",
        subject="Subject",
        body="Body",
    )

    result = await service.send(request=request)

    assert result.accepted is True
    assert result.provider == EmailProvider.RESEND
    assert provider.requests == [request]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_type", [EmailProvider.LEGACY, EmailProvider.SES])
async def test_production_email_service_rejects_non_resend_provider(
    provider_type: EmailProvider,
) -> None:
    service = EmailService(
        config=_config(provider_type, environment=EnvironmentType.PRODUCTION),
        providers={provider_type: _FakeProvider(provider_type)},
    )

    with pytest.raises(EmailConfigurationError, match="restricted to Resend"):
        await service.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment",
    [EnvironmentType.DEVELOPMENT, EnvironmentType.STAGING],
)
async def test_resend_is_rejected_outside_production(
    environment: EnvironmentType,
) -> None:
    service = EmailService(
        config=_config(EmailProvider.RESEND, environment=environment),
        providers={EmailProvider.RESEND: _FakeProvider(EmailProvider.RESEND)},
    )

    with pytest.raises(EmailConfigurationError, match="production-only"):
        await service.send(
            request=EmailRequest(
                to_email="user@example.com",
                subject="Subject",
                body="Body",
            )
        )


@pytest.mark.asyncio
async def test_email_service_rejects_unknown_provider() -> None:
    service = EmailService(
        config=_config("unknown"),
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
        config=_config(EmailProvider.SES),
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
