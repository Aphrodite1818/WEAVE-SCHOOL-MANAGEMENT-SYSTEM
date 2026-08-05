from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailProvider
from app.core.email.exceptions import EmailConfigurationError, EmailProviderError
from app.core.email.providers import legacy
from app.core.email.providers.legacy import LegacyEmailProvider


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        if self._payload is None:
            raise ValueError("No JSON response")
        return self._payload


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "APP_SCRIPT_URL": None,
        "SMTP_HOST": None,
        "SMTP_PORT": 587,
        "SMTP_FROM_EMAIL": None,
        "SMTP_PASSWORD": None,
        "EMAIL_REPLY_TO": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(*, is_html: bool = False) -> EmailRequest:
    return EmailRequest(
        to_email="user@example.com",
        subject="Subject",
        body="<p>Hello</p>" if is_html else "Hello",
        is_html=is_html,
    )


@pytest.mark.asyncio
async def test_apps_script_success_returns_accepted_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> _FakeResponse:
            return _FakeResponse(200, {"success": True})

    monkeypatch.setattr(legacy.httpx, "AsyncClient", FakeAsyncClient)
    provider = LegacyEmailProvider(
        config=_config(APP_SCRIPT_URL="https://script.example.com/exec")
    )

    result = await provider.send(request=_request())

    assert result.accepted is True
    assert result.provider == EmailProvider.LEGACY


@pytest.mark.asyncio
async def test_apps_script_non_json_200_does_not_trigger_duplicate_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> _FakeResponse:
            return _FakeResponse(200)

    class UnexpectedSMTP:
        def __init__(self, **_: object) -> None:
            raise AssertionError("SMTP fallback must not run after HTTP 200")

    monkeypatch.setattr(legacy.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(legacy.aiosmtplib, "SMTP", UnexpectedSMTP)
    provider = LegacyEmailProvider(
        config=_config(
            APP_SCRIPT_URL="https://script.example.com/exec",
            SMTP_HOST="smtp.example.com",
            SMTP_FROM_EMAIL="sender@example.com",
            SMTP_PASSWORD=SecretStr("password"),
        )
    )

    result = await provider.send(request=_request())

    assert result.accepted is True


@pytest.mark.asyncio
async def test_apps_script_failure_falls_back_to_smtp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> _FakeResponse:
            return _FakeResponse(503, {"success": False})

    class FakeSMTP:
        is_connected = True

        def __init__(self, **_: object) -> None:
            events.append("created")

        async def connect(self) -> None:
            events.append("connected")

        async def login(self, username: str, password: str) -> None:
            assert username == "sender@example.com"
            assert password == "password"
            events.append("authenticated")

        async def send_message(self, message: object) -> None:
            events.append("sent")

        async def quit(self) -> None:
            events.append("closed")

    monkeypatch.setattr(legacy.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(legacy.aiosmtplib, "SMTP", FakeSMTP)
    provider = LegacyEmailProvider(
        config=_config(
            APP_SCRIPT_URL="https://script.example.com/exec",
            SMTP_HOST="smtp.example.com",
            SMTP_FROM_EMAIL="sender@example.com",
            SMTP_PASSWORD=SecretStr("password"),
        )
    )

    result = await provider.send(request=_request(is_html=True))

    assert result.accepted is True
    assert events == [
        "created",
        "connected",
        "authenticated",
        "sent",
        "closed",
    ]


@pytest.mark.asyncio
async def test_missing_legacy_transports_raises_configuration_error() -> None:
    provider = LegacyEmailProvider(config=_config())

    with pytest.raises(EmailConfigurationError):
        await provider.send(request=_request())


@pytest.mark.asyncio
async def test_smtp_failure_raises_retryable_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSMTP:
        is_connected = False

        def __init__(self, **_: object) -> None:
            pass

        async def connect(self) -> None:
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(legacy.aiosmtplib, "SMTP", FakeSMTP)
    provider = LegacyEmailProvider(
        config=_config(
            SMTP_HOST="smtp.example.com",
            SMTP_FROM_EMAIL="sender@example.com",
            SMTP_PASSWORD=SecretStr("password"),
        )
    )

    with pytest.raises(EmailProviderError) as error_info:
        await provider.send(request=_request())

    assert error_info.value.provider == EmailProvider.LEGACY
    assert error_info.value.retryable is True
