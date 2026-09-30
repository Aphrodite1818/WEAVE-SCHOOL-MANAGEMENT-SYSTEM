from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.settings import ACTIVE_ENV_FILE, BASE_DIR


class AIQuotaPricingSettings(BaseSettings):
    """Environment-owned commercial settings for tenant AI-credit purchases."""

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ACTIVE_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Zero disables paid credit checkout until an explicit commercial price is set.
    CBT_AI_CREDIT_UNIT_PRICE_KOBO: int = Field(default=0, ge=0)
    CBT_AI_MINIMUM_PURCHASE_CREDITS: int = Field(default=1, gt=0)


ai_quota_pricing = AIQuotaPricingSettings()
