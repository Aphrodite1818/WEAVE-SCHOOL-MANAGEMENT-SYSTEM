from __future__ import annotations

import pytest

from app.core.email.contracts import EmailDeliveryResult, EmailRequest
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailProviderError
from app.core.utils import email


class _FakeEmailService:
    def __init__(
        self,
        *,
        result: EmailDeliveryResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.requests: list[EmailRequest] = []

    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        assert self.result is not None
        return self.result


@pytest.mark.asyncio
async def test_send_email_builds_request_and_preserves_boolean_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeEmailService(
        result=EmailDeliveryResult(
            provider=EmailProvider.SES,
            accepted=True,
            message_id="message-id",
        )
    )
    monkeypatch.setattr(email, "email_service", service)

    accepted = await email.send_email(
        "user@example.com",
        "Security notice",
        "<p>Review your account</p>",
        True,
        category=EmailCategory.SECURITY,
        reply_to="support@example.com",
        tags=(("email_type", "security_alert"),),
    )

    assert accepted is True
    assert len(service.requests) == 1
    request = service.requests[0]
    assert request.category == EmailCategory.SECURITY
    assert request.is_html is True
    assert request.reply_to == "support@example.com"
    assert request.tags == (("email_type", "security_alert"),)


@pytest.mark.asyncio
async def test_send_email_returns_false_for_structured_email_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeEmailService(
        error=EmailProviderError(
            "Delivery failed",
            provider=EmailProvider.SES,
            code="ServiceUnavailableException",
            retryable=True,
        )
    )
    monkeypatch.setattr(email, "email_service", service)

    accepted = await email.send_email(
        "user@example.com",
        "Subject",
        "Body",
    )

    assert accepted is False
