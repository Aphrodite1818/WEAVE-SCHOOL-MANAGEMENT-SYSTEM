# ========================== #
#    core/storage/local.py   #
# ========================== #

"""Local filesystem media storage backend for development."""

from __future__ import annotations

from pathlib import Path

import aiofiles

from app.config.settings import settings
from app.core.storage.base import StorageUploadResult
from app.modules.media.models import MediaVisibility


class LocalMediaStorage:
    """Local disk storage backend for development and testing."""

    def __init__(self) -> None:
        self.bucket = str(getattr(settings, "LOCAL_MEDIA_BUCKET_NAME", "local-media"))
        self.storage_root = Path(
            getattr(settings, "LOCAL_MEDIA_ROOT", "storage/media")
        ).resolve()
        self.public_base_url = str(
            getattr(settings, "LOCAL_MEDIA_PUBLIC_BASE_URL", "/media")
        ).rstrip("/")

    def _get_absolute_path(self, object_key: str) -> Path:
        """Resolve an object key into a safe absolute local path."""

        cleaned_key = object_key.strip().lstrip("/")

        if not cleaned_key:
            raise ValueError("Object key is required.")

        target_path = (self.storage_root / cleaned_key).resolve()

        if not str(target_path).startswith(str(self.storage_root)):
            raise ValueError("Invalid object key path.")

        return target_path

    def _build_public_url(self, object_key: str) -> str:
        """Build local public URL for an object."""

        cleaned_key = object_key.strip().lstrip("/")
        return f"{self.public_base_url}/{cleaned_key}"

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
        """Upload bytes to local disk."""

        target_path = self._get_absolute_path(object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(target_path, "wb") as file_obj:
            await file_obj.write(data)

        public_url = self._build_public_url(object_key)

        return StorageUploadResult(
            bucket=self.bucket,
            object_key=object_key,
            public_url=public_url,
            cdn_url=public_url,
            etag=None,
            metadata={
                "content_type": content_type,
                "visibility": visibility.value,
                "cache_control": cache_control,
                **(metadata or {}),
            },
        )

    async def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        """Delete an object from local disk."""

        target_path = self._get_absolute_path(object_key)

        if target_path.exists():
            target_path.unlink()

    async def create_signed_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int = 300,
    ) -> str:
        """Return a local render URL.

        Local development does not need real signed URLs.
        """

        return self._build_public_url(object_key)