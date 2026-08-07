# ========================== #
#     core/storage/keys.py   #
# ========================== #

"""Safe object-key generation for tenant media files."""

from __future__ import annotations

from uuid import UUID

from app.modules.media.models import MediaOwnerType, MediaPurpose


class StorageKeyError(ValueError):
    """Raised when a media object key cannot be generated."""


def _normalize_extension(extension: str) -> str:
    """Normalize a file extension for object-key usage."""

    cleaned_extension = extension.strip().lower().lstrip(".")

    if not cleaned_extension:
        raise StorageKeyError("File extension is required.")

    if cleaned_extension == "jpeg":
        return "jpg"

    return cleaned_extension


def build_media_object_key(
    *,
    tenant_id: UUID,
    owner_type: MediaOwnerType,
    owner_id: UUID,
    purpose: MediaPurpose,
    media_asset_id: UUID,
    extension: str,
) -> str:
    """Build a deterministic tenant-scoped storage object key."""

    normalized_extension = _normalize_extension(extension)

    if owner_type == MediaOwnerType.TENANT and purpose == MediaPurpose.SCHOOL_LOGO:
        return f"tenants/{tenant_id}/logos/{media_asset_id}.{normalized_extension}"

    if owner_type == MediaOwnerType.STUDENT and purpose == MediaPurpose.STUDENT_PASSPORT:
        return (
            f"tenants/{tenant_id}/students/{owner_id}/passport/"
            f"{media_asset_id}.{normalized_extension}"
        )

    if owner_type == MediaOwnerType.TEACHER and purpose == MediaPurpose.TEACHER_PASSPORT:
        return (
            f"tenants/{tenant_id}/teachers/{owner_id}/passport/"
            f"{media_asset_id}.{normalized_extension}"
        )

    if owner_type == MediaOwnerType.TENANT_ADMIN and purpose == MediaPurpose.TENANT_ADMIN_PASSPORT:
        return (
            f"tenants/{tenant_id}/tenant-admins/{owner_id}/passport/"
            f"{media_asset_id}.{normalized_extension}"
        )

    raise StorageKeyError(f"Unsupported owner/purpose pair: {owner_type.value}/{purpose.value}")
