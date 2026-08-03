from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.utils import email


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload or "")

    def json(self) -> dict[str, object]:
        if self._payload is None:
            raise ValueError("No JSON body")
        return self._payload


@pytest.mark.asyncio
async def test_app_script_sender_follows_google_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *, timeout: object, follow_redirects: bool) -> None:
            captured["timeout"] = timeout
            captured["follow_redirects"] = follow_redirects

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, object]) -> _FakeResponse:
            captured["url"] = url
            captured["payload"] = json
            return _FakeResponse(200, {"success": True})

    monkeypatch.setattr(email.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        email,
        "settings",
        SimpleNamespace(
            APP_SCRIPT_URL="https://script.google.com/macros/s/example/exec",
            SMTP_HOST=None,
            SMTP_PORT=587,
            SMTP_FROM_EMAIL=None,
            SMTP_PASSWORD=None,
        ),
    )

    result = await email.send_email("parent@example.com", "Subject", "Body")

    assert result is True
    assert captured["follow_redirects"] is True
    assert captured["url"] == "https://script.google.com/macros/s/example/exec"


@pytest.mark.asyncio
async def test_app_script_sender_rejects_success_false(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *, timeout: object, follow_redirects: bool) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, object]) -> _FakeResponse:
            return _FakeResponse(200, {"success": False, "message": "send failed"})

    monkeypatch.setattr(email.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        email,
        "settings",
        SimpleNamespace(
            APP_SCRIPT_URL="https://script.google.com/macros/s/example/exec",
            SMTP_HOST=None,
            SMTP_PORT=587,
            SMTP_FROM_EMAIL=None,
            SMTP_PASSWORD=None,
        ),
    )

    result = await email.send_email("parent@example.com", "Subject", "Body")

    assert result is False
