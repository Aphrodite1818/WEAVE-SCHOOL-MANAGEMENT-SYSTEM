from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def _production_values() -> dict[str, object]:
    return {
        "ENV": "prod",
        "SECRET_KEY": "s" * 64,
        "SENTRY_DSN": "https://public@example.invalid/1",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@db.example.com/weave",
        "REDIS_URL": "rediss://default:password@redis.example.com:6379/0",
        "FRONTEND_APP_URL": "https://app.weave.example",
        "ALLOWED_ORIGINS": ["https://app.weave.example"],
        "TRUST_PROXY_HEADERS": True,
        "TRUSTED_PROXY_HOPS": 1,
        "BULK_IMPORT_RESULT_ENCRYPTION_KEY": "b" * 64,
        "EMAIL_PROVIDER": "resend",
        "RESEND_API_KEY": "re_test_key",
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "MEDIA_STORAGE_PROVIDER": "r2",
        "R2_ACCOUNT_ID": "account",
        "R2_ACCESS_KEY_ID": "access-key",
        "R2_SECRET_ACCESS_KEY": "secret-key",
        "R2_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
        "R2_PUBLIC_URL": "https://media.weave.example",
    }


def test_valid_production_configuration_is_accepted() -> None:
    settings = Settings(_env_file=None, **_production_values())

    assert settings.is_production_like is True
    assert settings.EMAIL_PROVIDER == "resend"
    assert settings.MEDIA_STORAGE_PROVIDER == "r2"


def test_production_accepts_resend_without_aws_credentials() -> None:
    settings = Settings(_env_file=None, **_production_values())

    assert settings.EMAIL_PROVIDER == "resend"
    assert settings.AWS_ACCESS_KEY_ID is None
    assert settings.AWS_SECRET_ACCESS_KEY is None


def test_production_rejects_missing_resend_api_key() -> None:
    values = _production_values()
    values["RESEND_API_KEY"] = None

    with pytest.raises(
        ValidationError,
        match="Resend configuration is incomplete.*RESEND_API_KEY",
    ):
        Settings(_env_file=None, **values)


def test_production_rejects_missing_sentry_dsn() -> None:
    values = _production_values()
    values["SENTRY_DSN"] = None

    with pytest.raises(ValidationError, match="SENTRY_DSN is required in production"):
        Settings(_env_file=None, **values)


def test_production_rejects_wildcard_cors() -> None:
    values = _production_values()
    values["ALLOWED_ORIGINS"] = ["*"]

    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        Settings(_env_file=None, **values)


def test_production_rejects_ephemeral_local_media() -> None:
    values = _production_values()
    values["MEDIA_STORAGE_PROVIDER"] = "local"

    with pytest.raises(ValidationError, match="Production media storage must use R2"):
        Settings(_env_file=None, **values)
