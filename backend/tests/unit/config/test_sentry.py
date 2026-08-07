"""Tests for optional Sentry configuration and privacy controls."""

from __future__ import annotations

import json

from pydantic import SecretStr

from app.config import sentry as sentry_config
from app.config.settings import EnvironmentType, Settings


def test_sentry_credentials_are_optional() -> None:
    configured = Settings(
        _env_file=None,
        ENV="dev",
        SECRET_KEY="x" * 32,
        DATABASE_URL=(
            "postgresql+asyncpg://"
            "user:pass@localhost/weave"
        ),
        FRONTEND_APP_URL="http://localhost:5173",
        EMAIL_PROVIDER="legacy",
        APP_SCRIPT_URL=(
            "https://example.com/email-script"
        ),
    )

    assert configured.SENTRY_DSN is None
    assert configured.SENTRY_ERROR_SAMPLE_RATE == 1.0
    assert configured.SENTRY_TRACES_SAMPLE_RATE == 0.0


def test_initialize_sentry_is_disabled_without_dsn(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sentry_config.settings,
        "SENTRY_DSN",
        None,
    )

    def unexpected_init(**kwargs) -> None:
        raise AssertionError(
            f"Sentry init should not run: {kwargs}"
        )

    monkeypatch.setattr(
        sentry_config.sentry_sdk,
        "init",
        unexpected_init,
    )

    assert (
        sentry_config.initialize_sentry(
            service="api",
        )
        is False
    )


def test_initialize_sentry_failure_is_fail_open(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sentry_config.settings,
        "SENTRY_DSN",
        SecretStr(
            "https://public@example.invalid/1"
        ),
    )

    def failed_init(**kwargs) -> None:
        _ = kwargs
        raise RuntimeError("invalid DSN")

    monkeypatch.setattr(
        sentry_config.sentry_sdk,
        "init",
        failed_init,
    )

    assert (
        sentry_config.initialize_sentry(
            service="worker-heavy",
        )
        is False
    )


def test_initialize_sentry_uses_safe_defaults(
    monkeypatch,
) -> None:
    captured_options: dict[str, object] = {}

    monkeypatch.setattr(
        sentry_config.settings,
        "SENTRY_DSN",
        SecretStr(
            "https://public@example.invalid/1"
        ),
    )
    monkeypatch.setattr(
        sentry_config.settings,
        "ENV",
        EnvironmentType.STAGING,
    )
    monkeypatch.setattr(
        sentry_config.settings,
        "SENTRY_RELEASE",
        "weave@test",
    )

    monkeypatch.setattr(
        sentry_config.sentry_sdk,
        "init",
        captured_options.update,
    )
    monkeypatch.setattr(
        sentry_config.sentry_sdk,
        "set_tag",
        lambda *args: None,
    )
    monkeypatch.setattr(
        sentry_config.sentry_sdk,
        "set_context",
        lambda *args: None,
    )

    assert (
        sentry_config.initialize_sentry(
            service="api",
        )
        is True
    )

    assert captured_options["environment"] == "stg"
    assert captured_options["release"] == "weave@test"
    assert captured_options["send_default_pii"] is False
    assert captured_options["max_request_body_size"] == "never"
    assert captured_options["include_local_variables"] is False
    assert captured_options["enable_logs"] is False
    assert captured_options["enable_metrics"] is False
    assert captured_options["traces_sample_rate"] == 0.0


def test_before_send_removes_sensitive_values() -> None:
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer access-token",
                "Cookie": "session=secret",
                "X-Request-ID": "request-123",
            },
            "data": {
                "password": "password-value",
                "student_name": "Private Student",
            },
        },
        "user": {
            "id": "user-123",
            "email": "private@example.com",
            "ip_address": "127.0.0.1",
        },
        "contexts": {
            "email": {
                "parent_email": "parent@example.com",
                "access_code": "12345678",
            },
            "tenant": {
                "tenant_id": "tenant-123",
            },
        },
    }

    sanitized = sentry_config._before_send(
        event,
        {},
    )
    serialized = json.dumps(sanitized)

    assert sanitized is not None

    assert "access-token" not in serialized
    assert "session=secret" not in serialized
    assert "password-value" not in serialized
    assert "Private Student" not in serialized
    assert "private@example.com" not in serialized
    assert "parent@example.com" not in serialized
    assert "12345678" not in serialized

    assert "request-123" in serialized
    assert "tenant-123" in serialized
    assert "user-123" in serialized
