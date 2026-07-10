# =========================== #
#   core/storage/factory.py   #
# =========================== #

"""Factory for configured media storage backend."""

from __future__ import annotations

from functools import lru_cache

from app.config.settings import settings
from app.core.storage.base import MediaStorageBackend
from app.core.storage.local import LocalMediaStorage
from app.core.storage.r2 import CloudflareR2MediaStorage


class MediaStorageConfigurationError(RuntimeError):
    """Raised when media storage is misconfigured."""


@lru_cache(maxsize=1)
def get_media_storage() -> MediaStorageBackend:
    """Return the configured media storage backend."""

    provider = str(getattr(settings, "MEDIA_STORAGE_PROVIDER", "local")).strip().lower()

    if provider == "local":
        return LocalMediaStorage()

    if provider in {"cloudflare_r2", "r2", "cloudflare"}:
        return CloudflareR2MediaStorage()

    raise MediaStorageConfigurationError(
        f"Unsupported MEDIA_STORAGE_PROVIDER: {provider}"
    )


def reset_media_storage_cache() -> None:
    """Clear cached storage backend.

    Useful for tests where settings are patched.
    """

    get_media_storage.cache_clear()
