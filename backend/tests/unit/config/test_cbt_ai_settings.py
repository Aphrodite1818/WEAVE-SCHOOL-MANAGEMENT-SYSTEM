"""CBT AI configuration validation without external provider calls."""

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from app.config.settings import Settings


class IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (init_settings,)


def make_settings(**overrides):
    values = dict(
        SECRET_KEY="s" * 64,
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        FRONTEND_APP_URL="http://localhost:3000",
        EMAIL_PROVIDER="legacy",
        APP_SCRIPT_URL="https://example.invalid/exec",
    )
    values.update(overrides)
    return IsolatedSettings(**values)


def test_defaults_and_validator_chain():
    config = make_settings()
    assert config.MINIMAX_BASE_URL == "https://api.minimax.io"
    assert config.GEMINI_API_KEY is None
    assert config.MINIMAX_API_KEY is None
    assert config.OPENVERSE_CLIENT_ID is None
    assert config.OPENVERSE_CLIENT_SECRET is None
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        make_settings(DATABASE_URL=None)


@pytest.mark.parametrize(
    "field", ["CBT_AI_QUESTION_PROVIDER", "CBT_AI_IMAGE_PROVIDER", "CBT_AI_IMAGE_SEARCH_PROVIDER"]
)
def test_unknown_provider_rejected(field):
    with pytest.raises(ValidationError):
        make_settings(**{field: "unknown"})


@pytest.mark.parametrize("provider", ["gemini", "minimax"])
def test_supported_generation_providers(provider):
    assert (
        make_settings(
            CBT_AI_QUESTION_PROVIDER=provider, CBT_AI_IMAGE_PROVIDER=provider
        ).CBT_AI_QUESTION_PROVIDER
        == provider
    )


@pytest.mark.parametrize("field", ["MINIMAX_BASE_URL", "GEMINI_BASE_URL", "OPENVERSE_BASE_URL"])
@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://example.com",
        "https://",
        "https://bad host",
        "https://user:pass@example.com",
        "https://example.com?key=test",
        "https://example.com#fragment",
        "https://example.com:bad",
        "https://example.com:0",
        "https://[invalid",
        None,
    ],
)
def test_invalid_service_urls(field, value):
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_values_normalized_and_secrets_masked():
    config = make_settings(
        GEMINI_BASE_URL=" https://example.com/v1/ ",
        GEMINI_TEXT_MODEL=" model ",
        GEMINI_API_KEY=" example-test-key ",
    )
    assert config.GEMINI_BASE_URL == "https://example.com/v1"
    assert config.GEMINI_TEXT_MODEL == "model"
    assert isinstance(config.GEMINI_API_KEY, SecretStr)
    assert config.GEMINI_API_KEY.get_secret_value() == "example-test-key"
    assert "example-test-key" not in repr(config)


@pytest.mark.parametrize(
    "field",
    [
        "MINIMAX_TEXT_MODEL",
        "MINIMAX_IMAGE_MODEL",
        "GEMINI_TEXT_MODEL",
        "GEMINI_IMAGE_MODEL",
    ],
)
def test_blank_model_names_rejected(field):
    with pytest.raises(ValidationError):
        make_settings(**{field: "   "})


@pytest.mark.parametrize(
    "field",
    [
        "MINIMAX_API_KEY",
        "GEMINI_API_KEY",
        "OPENVERSE_CLIENT_SECRET",
    ],
)
def test_blank_optional_secrets_become_none(field):
    config = make_settings(**{field: "   "})
    assert getattr(config, field) is None


def test_blank_openverse_client_id_becomes_none():
    config = make_settings(OPENVERSE_CLIENT_ID="   ")
    assert config.OPENVERSE_CLIENT_ID is None


def test_partial_openverse_credentials_do_not_block_startup():
    id_only = make_settings(OPENVERSE_CLIENT_ID="client")
    secret_only = make_settings(OPENVERSE_CLIENT_SECRET="test-secret")

    assert id_only.OPENVERSE_CLIENT_ID == "client"
    assert id_only.OPENVERSE_CLIENT_SECRET is None
    assert secret_only.OPENVERSE_CLIENT_ID is None
    assert isinstance(secret_only.OPENVERSE_CLIENT_SECRET, SecretStr)


def test_complete_openverse_credentials():
    config = make_settings(OPENVERSE_CLIENT_ID=" client ", OPENVERSE_CLIENT_SECRET="test-secret")
    assert config.OPENVERSE_CLIENT_ID == "client"
    assert config.OPENVERSE_CLIENT_SECRET is not None


@pytest.mark.parametrize(
    "field,low,high",
    [
        ("MINIMAX_MAX_OUTPUT_TOKENS", 256, 131072),
        ("GEMINI_MAX_OUTPUT_TOKENS", 256, 131072),
        ("MINIMAX_IMAGE_TIMEOUT_SECONDS", 1, 300),
        ("MINIMAX_REQUEST_TIMEOUT_SECONDS", 1, 300),
        ("GEMINI_IMAGE_TIMEOUT_SECONDS", 1, 300),
        ("GEMINI_REQUEST_TIMEOUT_SECONDS", 1, 300),
        ("OPENVERSE_REQUEST_TIMEOUT_SECONDS", 1, 60),
    ],
)
def test_numeric_bounds(field, low, high):
    for value in (low, high):
        assert getattr(make_settings(**{field: value}), field) == value
    for value in (low - 1, high + 1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            make_settings(**{field: value})
