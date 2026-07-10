# ======================= #
#    core/storage/r2.py   #
# ======================= #

"""Cloudflare R2 media storage backend."""

from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import settings
from app.core.storage.base import StorageUploadResult
from app.modules.media.models import MediaVisibility


class CloudflareR2StorageError(RuntimeError):
    """Raised when Cloudflare R2 storage operations fail."""


class CloudflareR2MediaStorage:
    """Cloudflare R2 storage backend using the S3-compatible API."""

    def __init__(self) -> None:
        self.account_id = self._optional_setting("R2_ACCOUNT_ID")
        self.endpoint_url = self._resolve_endpoint_url()
        self.access_key_id = self._require_setting("R2_ACCESS_KEY_ID")
        self.secret_access_key = self._require_setting("R2_SECRET_ACCESS_KEY")
        self.bucket = self._require_setting("R2_BUCKET_NAME")
        self.public_base_url = self._resolve_public_base_url()

    @staticmethod
    def _require_setting(setting_name: str) -> str:
        """Return a required setting or raise a clear error."""

        value = getattr(settings, setting_name, None)

        if value is None or not str(value).strip():
            raise CloudflareR2StorageError(f"{setting_name} is not configured.")

        return str(value).strip()

    @staticmethod
    def _optional_setting(setting_name: str) -> str | None:
        """Return an optional setting."""

        value = getattr(settings, setting_name, None)

        if value is None:
            return None

        cleaned_value = str(value).strip().rstrip("/")
        return cleaned_value or None

    def _resolve_endpoint_url(self) -> str:
        """Resolve the R2 S3-compatible endpoint URL."""

        configured_endpoint = self._optional_setting("R2_ENDPOINT_URL")
        if configured_endpoint is not None:
            return configured_endpoint

        if self.account_id is None:
            raise CloudflareR2StorageError(
                "R2_ENDPOINT_URL or R2_ACCOUNT_ID must be configured."
            )

        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def _resolve_public_base_url(self) -> str | None:
        """Resolve the public/CDN base URL used to render stored media."""

        return self._optional_setting("MEDIA_PUBLIC_BASE_URL") or self._optional_setting(
            "R2_PUBLIC_URL"
        )

    @cached_property
    def client(self) -> Any:
        """Create a boto3 S3 client for Cloudflare R2."""

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    @staticmethod
    def _clean_object_key(object_key: str) -> str:
        """Normalize object key."""

        cleaned_key = object_key.strip().lstrip("/")

        if not cleaned_key:
            raise CloudflareR2StorageError("Object key is required.")

        return cleaned_key

    @staticmethod
    def _clean_metadata(metadata: dict[str, str] | None) -> dict[str, str]:
        """Normalize metadata values for S3/R2."""

        if not metadata:
            return {}

        cleaned_metadata: dict[str, str] = {}

        for key, value in metadata.items():
            cleaned_key = str(key).strip().lower().replace("_", "-")
            cleaned_value = str(value).strip()

            if cleaned_key and cleaned_value:
                cleaned_metadata[cleaned_key] = cleaned_value

        return cleaned_metadata

    def _build_render_url(self, object_key: str) -> str | None:
        """Build a stable public/CDN render URL when configured."""

        if self.public_base_url is None:
            return None

        return f"{self.public_base_url}/{object_key}"

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
        """Upload bytes to Cloudflare R2."""

        cleaned_key = self._clean_object_key(object_key)
        cleaned_metadata = self._clean_metadata(metadata)

        put_kwargs = {
            "Bucket": self.bucket,
            "Key": cleaned_key,
            "Body": data,
            "ContentType": content_type,
            "CacheControl": cache_control,
            "Metadata": cleaned_metadata,
        }

        try:
            response = await asyncio.to_thread(
                self.client.put_object,
                **put_kwargs,
            )
        except (BotoCoreError, ClientError) as exc:
            raise CloudflareR2StorageError(
                "Failed to upload object to Cloudflare R2."
            ) from exc

        etag_value = response.get("ETag")
        etag: str | None = etag_value.strip('"') if isinstance(etag_value, str) else None

        render_url = self._build_render_url(cleaned_key)

        return StorageUploadResult(
            bucket=self.bucket,
            object_key=cleaned_key,
            public_url=render_url,
            cdn_url=render_url,
            etag=etag,
            metadata={
                "visibility": visibility.value,
                "cache_control": cache_control,
                **cleaned_metadata,
            },
        )

    async def delete_object(
        self,
        *,
        object_key: str,
    ) -> None:
        """Delete an object from Cloudflare R2."""

        cleaned_key = self._clean_object_key(object_key)

        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=self.bucket,
                Key=cleaned_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise CloudflareR2StorageError(
                "Failed to delete object from Cloudflare R2."
            ) from exc

    async def create_signed_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int = 300,
    ) -> str:
        """Create a temporary signed URL for a private R2 object."""

        cleaned_key = self._clean_object_key(object_key)

        try:
            return await asyncio.to_thread(
                self.client.generate_presigned_url,
                ClientMethod="get_object",
                Params={"Bucket": self.bucket, "Key": cleaned_key},
                ExpiresIn=expires_in_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise CloudflareR2StorageError(
                "Failed to create signed URL for Cloudflare R2 object."
            ) from exc
