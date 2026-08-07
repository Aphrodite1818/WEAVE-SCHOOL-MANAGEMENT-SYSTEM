# ==========================#
#      core.cache.base     #
# ==========================#
"""Helpers for building clean, deterministic cache keys."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_cache_part(value: Any) -> str:
    """
    Convert one cache-key segment into a stable string representation.

    Example:
    UUID("...") -> "..."
    None -> "none"
    True -> "true"
    """

    if value is None:
        return "none"

    if isinstance(value, bool):
        return str(value).lower()

    return str(value).strip()


def tenant_prefix(tenant_id: str) -> str:
    """
    Build the prefix used for tenant-scoped cache keys.

    Every tenant-specific cache key should start with this prefix.
    """

    return f"tenant:{normalize_cache_part(tenant_id)}"


def global_prefix() -> str:
    """
    Build the prefix used for cache keys that are not tenant-scoped.
    """

    return "global"


def normalize_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize query or filter parameters before hashing.

    This helps make sure these two produce the same cache key:
    {"search": "", "limit": 100}
    {"limit": 100, "search": ""}

    because dictionary order should not affect the cache key.
    """

    if not params:
        return {}

    normalized: dict[str, Any] = {}

    for key, value in params.items():
        if value is None:
            continue

        if value == "":
            continue

        normalized[str(key)] = value

    return normalized


def hash_params(params: dict[str, Any] | None) -> str:
    """
    Hash normalized query or filter parameters into a short cache segment.

    This helps make sure these two produce the same cache key:
    {"search": "", "limit": 100}
    {"limit": 100, "search": ""}

    because dictionary order should not affect the cache key.
    """

    normalized = normalize_params(params)

    if not normalized:
        return "default"

    raw = json.dumps(
        normalized,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def build_cache_key(*parts: Any) -> str:
    """
    Build a clean cache key from multiple parts.

    Example:
    build_cache_key("tenant:123", "user", 456, "profile") -> "tenant:123:user:456:profile"
    """

    cleaned_parts = [
        normalize_cache_part(part)
        for part in parts
        if part is not None and str(part).strip() != ""
    ]

    return ":".join(cleaned_parts)
