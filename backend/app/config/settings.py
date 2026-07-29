# ====================================== #
#             settings.py                #
# ====================================== #

"""Load and validate application settings from environment variables."""

import os
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import dotenv_values
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASE_ENV_VALUES = dotenv_values(BASE_DIR / ".env")
ACTIVE_ENV = (
    os.getenv("ENV")
    or os.getenv("APP_ENV")
    or BASE_ENV_VALUES.get("ENV")
    or "dev"
).lower()

ENV_FILE_BY_NAME = {
    "dev": ".env.development",
    "development": ".env.development",
    "prod": ".env.production",
    "production": ".env.production",
    "stg": ".env.staging",
    "staging": ".env.staging",
}
ACTIVE_ENV_FILE = ENV_FILE_BY_NAME.get(ACTIVE_ENV, f".env.{ACTIVE_ENV}")


class EnvironmentType(str, Enum):
    """Supported application environments."""

    DEVELOPMENT = "dev"
    PRODUCTION = "prod"
    STAGING = "stg"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(
            BASE_DIR / ".env",
            BASE_DIR / ACTIVE_ENV_FILE,
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    ENV: EnvironmentType = EnvironmentType.DEVELOPMENT
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None

    APP_NAME: str = "School Management System"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    DEFAULT_SESSION_DAYS: int = Field(default=7, gt=0)
    REMEMBER_ME_SESSION_DAYS: int = Field(default=30, gt=0)

    DATABASE_URL: str | None = Field(default=None, description="PostgreSQL connection URL")
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0, le=100)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=120)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60)

    GEMINI_API_KEY: str | None = Field(default=None, description="Api Key for Gemini")
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str | None = Field(default=None, description="Api Key for OpenAI")
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = Field(default=None, description="Api Key for Anthropic")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    LLM_MAX_TOKENS: int = 1024

    ALLOWED_ORIGINS: list[str] = Field(default_factory=list)

    TWILIO_ACCOUNT_SID: str | None = Field(default=None, description="Twilio account SID")
    TWILIO_AUTH_TOKEN: str | None = Field(default=None, description="Twilio auth token")
    TWILIO_WHATSAPP_FROM: str | None = Field(default=None, description="Twilio WhatsApp number")

    SMTP_HOST: str | None = Field(default=None, description="SMTP Server Host")
    SMTP_PORT: int = Field(default=587, description="SMTP Server Port")
    SMTP_PASSWORD: str | None = Field(default=None, description="SMTP Password")
    SMTP_FROM_EMAIL: str | None = Field(default=None, description="Sender Email Address")

    SECURITY_ALERTS_ENABLED: bool = Field(default=True)
    SECURITY_ALERT_EMAIL: str | None = Field(default=None)

    OTP_EXPIRATION_MINUTES: int = 10
    TENANT_ACTIVATION_EXPIRATION_HOURS: int = 48

    FRONTEND_APP_URL: str = Field(..., description="Frontend application URL")
    EMAIL_BRAND_LOGO_URL: str | None = Field(default=None)
    STUDENT_ACCESS_CODE_EXPIRY_HOURS: int = 48
    STUDENT_ACCESS_CODE_LENGTH: int = 8

    BULK_IMPORT_RESULT_ENCRYPTION_KEY: str | None = Field(
        default=None,
        description="Dedicated secret used to encrypt temporary imported student setup codes.",
    )
    BULK_IMPORT_SETUP_CODE_RETENTION_HOURS: int = Field(default=24, ge=1, le=168)
    BULK_IMPORT_STALE_AFTER_MINUTES: int = Field(default=20, ge=5, le=180)

    APP_SCRIPT_URL: str | None = Field(default=None)

    PAYSTACK_SECRET_KEY: str | None = Field(default=None)
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PAYSTACK_CALLBACK_URL: str | None = None
    PAYSTACK_PLUS_MONTHLY_PLAN_CODE: str | None = None
    PAYSTACK_PROFESSIONAL_MONTHLY_PLAN_CODE: str | None = None
    PAYSTACK_ENTERPRISE_MONTHLY_PLAN_CODE: str | None = None
    PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO: int | None = Field(default=1500000, ge=0)
    PAYSTACK_PROFESSIONAL_MONTHLY_AMOUNT_KOBO: int | None = Field(default=3500000, ge=0)
    PAYSTACK_ENTERPRISE_MONTHLY_AMOUNT_KOBO: int | None = Field(default=8000000, ge=0)

    REDIS_URL: str | None = Field(default=None, description="Redis connection URL")
    CACHE_ENABLED: bool = Field(default=False)
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REDIS_URL: str | None = Field(default=None)

    LOGIN_IP_LIMIT_5M: int = Field(default=20, gt=0)
    LOGIN_IP_LIMIT_1H: int = Field(default=100, gt=0)
    LOGIN_IDENTIFIER_FAIL_LIMIT_10M: int = Field(default=5, gt=0)
    LOGIN_IDENTIFIER_FAIL_LIMIT_1H: int = Field(default=15, gt=0)
    LOGIN_IDENTIFIER_IP_FAIL_LIMIT_10M: int = Field(default=5, gt=0)
    OTP_EMAIL_COOLDOWN_SECONDS: int = Field(default=60, gt=0)
    OTP_EMAIL_LIMIT_10M: int = Field(default=5, gt=0)
    OTP_EMAIL_LIMIT_24H: int = Field(default=12, gt=0)
    OTP_IP_LIMIT_1H: int = Field(default=20, gt=0)
    OTP_VERIFY_EMAIL_FAIL_LIMIT_10M: int = Field(default=5, gt=0)
    OTP_VERIFY_IP_FAIL_LIMIT_1H: int = Field(default=30, gt=0)

    CACHE_DEFAULT_TTL_SECONDS: int = Field(default=300, gt=0)
    CACHE_SHORT_TTL_SECONDS: int = Field(default=60, gt=0)
    CACHE_LONG_TTL_SECONDS: int = Field(default=1800, gt=0)

    MEDIA_STORAGE_PROVIDER: Literal["local", "r2"] = "local"
    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    R2_ENDPOINT_URL: str | None = None
    R2_BUCKET_NAME: str = "weave-public-media"
    R2_PUBLIC_URL: str | None = None
    MEDIA_PUBLIC_BASE_URL: str | None = None
    MEDIA_MAX_LOGO_SIZE_BYTES: int = 1 * 1024 * 1024
    MEDIA_MAX_PASSPORT_SIZE_BYTES: int = 2 * 1024 * 1024
    MEDIA_ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]

    @field_validator(
        "CACHE_DEFAULT_TTL_SECONDS",
        "CACHE_SHORT_TTL_SECONDS",
        "CACHE_LONG_TTL_SECONDS",
        mode="before",
    )
    @classmethod
    def parse_cache_ttl(cls, value: object) -> int:
        """Allow cache TTL values to be supplied as plain seconds in env files."""

        if value is None or value == "":
            raise ValueError("Cache TTL values cannot be empty.")
        if isinstance(value, timedelta):
            return int(value.total_seconds())
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                raise ValueError("Cache TTL values cannot be blank.")
            return int(float(raw_value))
        raise ValueError("Cache TTL values must be seconds.")

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Fail fast when runtime configuration is unsafe or incomplete."""

        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set for the active environment.")

        if self.CACHE_ENABLED and not self.REDIS_URL:
            raise ValueError("REDIS_URL must be set when CACHE_ENABLED is true.")

        if not (
            self.CACHE_SHORT_TTL_SECONDS
            <= self.CACHE_DEFAULT_TTL_SECONDS
            <= self.CACHE_LONG_TTL_SECONDS
        ):
            raise ValueError(
                "CACHE_TTL values must satisfy CACHE_SHORT_TTL_SECONDS <= "
                "CACHE_DEFAULT_TTL_SECONDS <= CACHE_LONG_TTL_SECONDS."
            )

        if not self.is_production_like:
            return self

        if len(self.SECRET_KEY.strip()) < 48:
            raise ValueError("SECRET_KEY must contain at least 48 characters in staging/production.")
        if not self.REDIS_URL:
            raise ValueError("REDIS_URL is required in staging/production for queues and rate limiting.")
        if self.RATE_LIMIT_ENABLED and not (self.RATE_LIMIT_REDIS_URL or self.REDIS_URL):
            raise ValueError("Redis must be configured when production rate limiting is enabled.")
        if not self.BULK_IMPORT_RESULT_ENCRYPTION_KEY or len(
            self.BULK_IMPORT_RESULT_ENCRYPTION_KEY.strip()
        ) < 32:
            raise ValueError(
                "BULK_IMPORT_RESULT_ENCRYPTION_KEY must contain at least 32 characters in staging/production."
            )
        if not self.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS must contain explicit HTTPS origins in staging/production.")
        if "*" in self.ALLOWED_ORIGINS:
            raise ValueError("Wildcard CORS origins are forbidden in staging/production.")
        for origin in self.ALLOWED_ORIGINS:
            parsed = urlparse(origin)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(
                    f"Production CORS origin must be an absolute HTTPS URL: {origin}"
                )
        frontend_url = urlparse(self.FRONTEND_APP_URL)
        if frontend_url.scheme != "https" or not frontend_url.netloc:
            raise ValueError("FRONTEND_APP_URL must be an absolute HTTPS URL in staging/production.")

        return self

    @property
    def is_development(self) -> bool:
        return self.ENV == EnvironmentType.DEVELOPMENT

    @property
    def is_production_like(self) -> bool:
        return self.ENV in {EnvironmentType.STAGING, EnvironmentType.PRODUCTION}


settings = Settings()  # pyright: ignore[reportCallIssue]
