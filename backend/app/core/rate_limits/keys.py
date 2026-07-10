from __future__ import annotations

import hashlib
import hmac

from app.config.settings import settings


def normalize_identifier(value: str) -> str:
    """Normalize login identifiers before hashing."""

    raw_value = value.strip()
    return raw_value.lower() if "@" in raw_value else raw_value


def digest_key_part(value: str) -> str:
    """Return a stable, non-reversible digest for sensitive key parts."""

    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_rate_limit_key(*parts: str) -> str:
    """Build a Redis key for rate-limit counters."""

    cleaned_parts = [str(part).strip().replace(":", "_") for part in parts if part]
    return "rl:" + ":".join(cleaned_parts)
