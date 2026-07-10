# ========================== #
#     core/storage/base.py   #
# ========================== #

"""Storage backend contracts for media uploads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.modules.media.models import MediaVisibility


@dataclass(frozen=True, slots=True)
class StorageUploadResult:
    """Normalized result returned after an object upload."""

    bucket: str
    object_key: str
    public_url: str | None = None
    cdn_url: str | None = None
    etag: str | None = None
    metadata: dict[str, str] | None = None


class MediaStorageBackend(Protocol):
    """Contract every media storage backend must implement."""

    async def upload_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str,
        visibility: MediaVisibility,
        cache_control: str,
        metadata: dict[str, str] | None = None,
    ) -> StorageUploadResult:
        """Upload bytes to storage."""

    async def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        """Delete an object from storage."""

    async def create_signed_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int = 300,
    ) -> str:
        """Create a temporary URL for private media."""
