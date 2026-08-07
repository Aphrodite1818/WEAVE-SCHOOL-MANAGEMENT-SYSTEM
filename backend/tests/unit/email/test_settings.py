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
        "RESEND_API_KEY": None,
        "RESEND_BASE_URL": "https://api.resend.com",
        "RESEND_TRANSACTIONAL_FROM_EMAIL": "no-reply@weavecloudspace.com",
        "RESEND_SECURITY_FROM_EMAIL": "security@weavecloudspace.com",
        "RESEND_BULK_FROM_EMAIL": "updates@weavecloudspace.com",
        "RESEND_TIMEOUT_SECONDS": 10.0,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_staging_can_use_legacy_without_external_provider_credentials() -> None:
    config = _settings(ENV=EnvironmentType.STAGING)

    assert config.validate_email_provider_settings() is config


def test_production_rejects_legacy_provider() -> None:
    config = _settings(ENV=EnvironmentType.PRODUCTION)

    with pytest.raises(ValueError, match="Production email provider must be 'resend'"):
        config.validate_email_provider_settings()


def test_ses_provider_requires_credentials_when_selected_outside_production() -> None:
    config = _settings(
        EMAIL_PROVIDER="ses",
        APP_SCRIPT_URL=None,
    )

    with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID"):
        config.validate_email_provider_settings()


def test_staging_accepts_complete_ses_configuration_for_future_use() -> None:
    config = _settings(
        ENV=EnvironmentType.STAGING,
        EMAIL_PROVIDER="ses",
        APP_SCRIPT_URL=None,
        AWS_ACCESS_KEY_ID="access-key",
        AWS_SECRET_ACCESS_KEY=SecretStr("secret-key"),
    )

    assert config.validate_email_provider_settings() is config


def test_production_rejects_ses_even_when_credentials_are_complete() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="ses",
        APP_SCRIPT_URL=None,
        AWS_ACCESS_KEY_ID="access-key",
        AWS_SECRET_ACCESS_KEY=SecretStr("secret-key"),
    )

    with pytest.raises(ValueError, match="Production email provider must be 'resend'"):
        config.validate_email_provider_settings()


def test_resend_provider_requires_api_key_in_production() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="resend",
        APP_SCRIPT_URL=None,
    )

    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        config.validate_email_provider_settings()


def test_production_accepts_resend_without_aws_credentials() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="resend",
        APP_SCRIPT_URL=None,
        RESEND_API_KEY=SecretStr("re_test_key"),
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
    )

    assert config.validate_email_provider_settings() is config


@pytest.mark.parametrize(
    "environment",
    [EnvironmentType.DEVELOPMENT, EnvironmentType.STAGING],
)
def test_resend_is_rejected_outside_production(environment: EnvironmentType) -> None:
    config = _settings(
        ENV=environment,
        EMAIL_PROVIDER="resend",
        APP_SCRIPT_URL=None,
        RESEND_API_KEY=SecretStr("re_test_key"),
    )

    with pytest.raises(ValueError, match="production-only"):
        config.validate_email_provider_settings()


def test_resend_rejects_non_https_base_url() -> None:
    config = _settings(
        ENV=EnvironmentType.PRODUCTION,
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY=SecretStr("re_test_key"),
        RESEND_BASE_URL="http://api.resend.com",
    )

    with pytest.raises(ValueError, match="RESEND_BASE_URL"):
        config.validate_email_provider_settings()


def test_partial_smtp_configuration_is_rejected() -> None:
    config = _settings(
        APP_SCRIPT_URL=None,
        SMTP_HOST="smtp.example.com",
    )

    with pytest.raises(ValueError, match="SMTP configuration is incomplete"):
        config.validate_email_provider_settings()
