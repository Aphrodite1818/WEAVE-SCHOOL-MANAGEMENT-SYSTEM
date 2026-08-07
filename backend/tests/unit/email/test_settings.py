from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.config.settings import EnvironmentType, Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "ENV": EnvironmentType.DEVELOPMENT,
        "EMAIL_PROVIDER": "legacy",
        "EMAIL_SENDER_NAME": "WEAVE",
        "EMAIL_REPLY_TO": None,
        "APP_SCRIPT_URL": "https://script.example.com/exec",
        "SMTP_HOST": None,
        "SMTP_PORT": 587,
        "SMTP_FROM_EMAIL": None,
        "SMTP_PASSWORD": None,
        "RESEND_API_KEY": None,
        "RESEND_TRANSACTIONAL_FROM_EMAIL": "no-reply@notifications.weavecloudspace.com",
        "RESEND_SECURITY_FROM_EMAIL": "security@notifications.weavecloudspace.com",
        "RESEND_BULK_FROM_EMAIL": "updates@updates.weavecloudspace.com",
        "AWS_REGION": "eu-west-1",
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "AWS_SESSION_TOKEN": None,
        "AWS_SES_ENDPOINT_URL": None,
        "SES_TRANSACTIONAL_FROM_EMAIL": "no-reply@notifications.weavecloudspace.com",
        "SES_SECURITY_FROM_EMAIL": "security@notifications.weavecloudspace.com",
        "SES_BULK_FROM_EMAIL": "updates@updates.weavecloudspace.com",
        "SES_TRANSACTIONAL_CONFIGURATION_SET": "weave-transactional",
        "SES_SECURITY_CONFIGURATION_SET": "weave-security",
        "SES_BULK_CONFIGURATION_SET": "weave-bulk",
        "SES_CONNECT_TIMEOUT_SECONDS": 5,
        "SES_READ_TIMEOUT_SECONDS": 10,
        "SES_MAX_ATTEMPTS": 3,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_staging_can_use_legacy_without_aws_credentials() -> None:
    config = _settings(ENV=EnvironmentType.STAGING)
    assert config.validate_email_provider_settings() is config


def test_production_requires_resend_provider() -> None:
    config = _settings(ENV=EnvironmentType.PRODUCTION, EMAIL_PROVIDER="legacy")
    with pytest.raises(ValueError, match="Production must use Resend"):
        config.validate_email_provider_settings()


def test_production_requires_resend_api_key() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="resend",
        APP_SCRIPT_URL=None,
    )
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        config.validate_email_provider_settings()


def test_production_accepts_complete_resend_configuration_without_aws() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="resend",
        APP_SCRIPT_URL=None,
        RESEND_API_KEY=SecretStr("re_production_key"),
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
    )
    assert config.validate_email_provider_settings() is config


def test_resend_is_rejected_outside_production() -> None:
    config = _settings(
        ENV=EnvironmentType.STAGING,
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY=SecretStr("re_staging_key"),
    )
    with pytest.raises(ValueError, match="only in production"):
        config.validate_email_provider_settings()


def test_ses_credentials_are_not_startup_mandatory() -> None:
    config = _settings(EMAIL_PROVIDER="ses", APP_SCRIPT_URL=None)
    assert config.validate_email_provider_settings() is config


def test_partial_smtp_configuration_is_rejected() -> None:
    config = _settings(APP_SCRIPT_URL=None, SMTP_HOST="smtp.example.com")
    with pytest.raises(ValueError, match="SMTP configuration is incomplete"):
        config.validate_email_provider_settings()
