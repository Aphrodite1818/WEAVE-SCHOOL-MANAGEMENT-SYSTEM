# ==========================#
#     media.validators     #
# ==========================#
"""Input validation helpers for the media module.

This file will hold reusable validation rules for uploaded files,
metadata, and any media-specific constraints.
"""

from __future__ import annotations
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config.settings import settings
from app.modules.media.models import MediaPurpose, MediaVisibility

DEFAULT_ALLOWED_IMAGE_TYPES: Final[set[str]] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

IMAGE_FORMAT_TO_CONTENT_TYPE: Final[dict[str, str]] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

CONTENT_TYPE_TO_EXTENSION: Final[dict[str, str]] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


ALLOWED_EXTENSIONS: Final[set[str]] = {"jpg", "jpeg", "png", "webp"}


PASSPORT_PURPOSES: Final[set[MediaPurpose]] = {
    MediaPurpose.STUDENT_PASSPORT,
    MediaPurpose.TEACHER_PASSPORT,
    MediaPurpose.TENANT_ADMIN_PASSPORT,
}

PUBLIC_PURPOSES: Final[set[MediaPurpose]] = {
    MediaPurpose.SCHOOL_LOGO,
}

PRIVATE_PURPOSES: Final[set[MediaPurpose]] = {
    MediaPurpose.STUDENT_PASSPORT,
    MediaPurpose.TEACHER_PASSPORT,
    MediaPurpose.TENANT_ADMIN_PASSPORT,
}


Image.MAX_IMAGE_PIXELS = 20_000_000


class MediaValidationError(ValueError):
    """Raised when an uploaded media file fails validation"""

    def __init__(self, message: str, *, code: str = "Invalid_media_upload") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ValidatedMediaFile:
    """Normalized file payload after upload validation"""

    original_filename: str | None
    content_type: str
    extension: str
    size_bytes: int
    checksum_sha256: str
    width_px: int
    height_px: int
    data: bytes


def _get_allowed_image_types() -> set[str]:
    """Return allowed set of image MIME types from settings"""

    raw_value = getattr(settings, "MEDIA_ALLOWED_IMAGE_TYPES", None)

    if raw_value is None:
        return set(DEFAULT_ALLOWED_IMAGE_TYPES)

    if isinstance(raw_value, str):
        return {item.strip().lower() for item in raw_value.split(",") if item.strip()}

    return {str(item).strip().lower() for item in raw_value if str(item).strip()}


def _get_max_logo_size_bytes() -> int:
    """Return max allowed logo size in bytes."""

    return int(getattr(settings, "MEDIA_MAX_LOGO_SIZE_BYTES", 1 * 1024 * 1024))


def _get_max_passport_size_bytes() -> int:
    """Return max allowed passport image size in bytes."""

    return int(getattr(settings, "MEDIA_MAX_PASSPORT_SIZE_BYTES", 2 * 1024 * 1024))


def _normalize_filename(filename: str | None) -> str | None:
    """Normalize an uploaded filename."""

    if filename is None:
        return None

    cleaned_filename = filename.strip()
    return cleaned_filename or None


def _extract_extension(filename: str | None) -> None | str:
    """Extract a normalized extension from a filename"""

    if not filename:
        return None

    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix or None


def _normalize_content_type(content_type: str | None) -> str | None:
    """Normalize browser-provided content type."""

    if content_type is None:
        return None

    cleaned_content_type = content_type.strip().lower()
    return cleaned_content_type or None


def _get_max_size_for_purpose(purpose: MediaPurpose) -> int:
    """Return the max file size for a media purpose."""

    if purpose == MediaPurpose.SCHOOL_LOGO:
        return _get_max_logo_size_bytes()

    if purpose in PASSPORT_PURPOSES:
        return _get_max_passport_size_bytes()

    raise MediaValidationError(
        f"Unsupported media purpose: {purpose!s}",
        code="unsupported_media_purpose",
    )


def _validate_supported_purpose(purpose: MediaPurpose) -> None:
    """Validate that the media purpose is supported by the media module."""

    supported_purposes = PUBLIC_PURPOSES | PRIVATE_PURPOSES

    if purpose not in supported_purposes:
        raise MediaValidationError(
            f"Unsupported media purpose: {purpose!s}",
            code="unsupported_media_purpose",
        )


def _validate_file_present(file: UploadFile) -> None:
    """Validate that an upload file was provided."""

    if file is None:
        raise MediaValidationError(
            "No file was uploaded.",
            code="missing_file",
        )


def _validate_filename(filename: str | None) -> None:
    """Validate filename and extension."""

    if filename is None:
        return

    extension = _extract_extension(filename)

    if extension is None:
        raise MediaValidationError(
            "Uploaded file must have a valid image extension.",
            code="missing_file_extension",
        )

    if extension not in ALLOWED_EXTENSIONS:
        raise MediaValidationError(
            "Unsupported file extension. Allowed extensions are jpg, jpeg, png, and webp.",
            code="unsupported_file_extension",
        )


def _validate_size(file_bytes: bytes, *, max_size_bytes: int) -> None:
    """Validate file size."""

    size_bytes = len(file_bytes)

    if size_bytes <= 0:
        raise MediaValidationError(
            "Uploaded file is empty.",
            code="empty_file",
        )

    if size_bytes > max_size_bytes:
        max_size_mb = max_size_bytes / (1024 * 1024)
        raise MediaValidationError(
            f"Uploaded file is too large. Maximum allowed size is {max_size_mb:.1f} MB.",
            code="file_too_large",
        )


def _validate_content_type_allowed(content_type: str) -> None:
    """Validate effective MIME type."""

    allowed_image_types = _get_allowed_image_types()

    if content_type not in allowed_image_types:
        allowed_types = ", ".join(sorted(allowed_image_types))
        raise MediaValidationError(
            f"Unsupported image type. Allowed types are: {allowed_types}.",
            code="unsupported_content_type",
        )


def _validate_extension_matches_content_type(
    *,
    extension: str | None,
    content_type: str,
) -> None:
    """Validate that filename extension is compatible with detected MIME type."""

    if extension is None:
        return

    normalized_extension = "jpg" if extension == "jpeg" else extension
    expected_extension = CONTENT_TYPE_TO_EXTENSION.get(content_type)

    if expected_extension is None:
        raise MediaValidationError(
            "Unsupported image content type.",
            code="unsupported_content_type",
        )

    if normalized_extension != expected_extension:
        raise MediaValidationError(
            "Uploaded file extension does not match the actual image type.",
            code="extension_content_type_mismatch",
        )


def _detect_image_metadata(file_bytes: bytes) -> tuple[str, int, int]:
    """Decode image bytes and return detected MIME type, width, and height."""

    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            image.verify()

        with Image.open(io.BytesIO(file_bytes)) as image:
            image_format = image.format
            width_px, height_px = image.size

    except UnidentifiedImageError as exc:
        raise MediaValidationError(
            "Uploaded file is not a valid image.",
            code="invalid_image",
        ) from exc
    except OSError as exc:
        raise MediaValidationError(
            "Uploaded image could not be processed.",
            code="image_processing_failed",
        ) from exc

    if image_format is None:
        raise MediaValidationError(
            "Unable to detect image format.",
            code="unknown_image_format",
        )

    content_type = IMAGE_FORMAT_TO_CONTENT_TYPE.get(image_format.upper())

    if content_type is None:
        raise MediaValidationError(
            "Unsupported image format. Allowed formats are JPEG, PNG, and WebP.",
            code="unsupported_image_format",
        )

    if width_px <= 0 or height_px <= 0:
        raise MediaValidationError(
            "Uploaded image has invalid dimensions.",
            code="invalid_image_dimensions",
        )

    return content_type, width_px, height_px


def _validate_dimensions(
    *,
    purpose: MediaPurpose,
    width_px: int,
    height_px: int,
) -> None:
    """Validate purpose-specific image dimensions."""

    if purpose == MediaPurpose.SCHOOL_LOGO:
        min_width = int(getattr(settings, "MEDIA_MIN_LOGO_WIDTH_PX", 64))
        min_height = int(getattr(settings, "MEDIA_MIN_LOGO_HEIGHT_PX", 64))
        max_width = int(getattr(settings, "MEDIA_MAX_LOGO_WIDTH_PX", 4000))
        max_height = int(getattr(settings, "MEDIA_MAX_LOGO_HEIGHT_PX", 4000))
    else:
        min_width = int(getattr(settings, "MEDIA_MIN_PASSPORT_WIDTH_PX", 120))
        min_height = int(getattr(settings, "MEDIA_MIN_PASSPORT_HEIGHT_PX", 120))
        max_width = int(getattr(settings, "MEDIA_MAX_PASSPORT_WIDTH_PX", 4000))
        max_height = int(getattr(settings, "MEDIA_MAX_PASSPORT_HEIGHT_PX", 4000))

    if width_px < min_width or height_px < min_height:
        raise MediaValidationError(
            f"Uploaded image is too small. Minimum dimensions are {min_width}x{min_height}px.",
            code="image_too_small",
        )

    if width_px > max_width or height_px > max_height:
        raise MediaValidationError(
            f"Uploaded image is too large. Maximum dimensions are {max_width}x{max_height}px.",
            code="image_dimensions_too_large",
        )


def _calculate_sha256(file_bytes: bytes) -> str:
    """Calculate SHA-256 checksum for file bytes."""

    return hashlib.sha256(file_bytes).hexdigest()


def _get_effective_extension(
    *,
    original_extension: str | None,
    detected_content_type: str,
) -> str:
    """Return the normalized extension used for storage metadata."""

    detected_extension = CONTENT_TYPE_TO_EXTENSION.get(detected_content_type)

    if detected_extension is None:
        raise MediaValidationError(
            "Unable to determine storage extension for image.",
            code="unknown_storage_extension",
        )

    if original_extension is None:
        return detected_extension

    normalized_original_extension = (
        "jpg" if original_extension.lower() == "jpeg" else original_extension.lower()
    )

    return normalized_original_extension


def get_visibility_for_purpose(purpose: MediaPurpose) -> MediaVisibility:
    """Return the intended visibility for a media purpose."""

    _validate_supported_purpose(purpose)

    if purpose in PUBLIC_PURPOSES:
        return MediaVisibility.PUBLIC

    return MediaVisibility.PRIVATE


def get_cache_control_for_purpose(purpose: MediaPurpose) -> str:
    """Return the recommended Cache-Control value for a media purpose."""

    _validate_supported_purpose(purpose)

    if purpose == MediaPurpose.SCHOOL_LOGO:
        return "public, max-age=31536000, immutable"

    return "private, max-age=300"


async def read_upload_bytes(file: UploadFile) -> bytes:
    """Read an UploadFile into memory and reset its cursor."""

    file_bytes = await file.read()

    try:
        await file.seek(0)
    except Exception:
        # Some UploadFile backends may not support seek cleanly.
        # The service should use returned bytes instead of re-reading the file.
        pass

    return file_bytes


async def validate_uploaded_image(
    *,
    file: UploadFile,
    purpose: MediaPurpose,
) -> ValidatedMediaFile:
    """Validate an uploaded image and return normalized metadata plus bytes."""

    _validate_supported_purpose(purpose)
    _validate_file_present(file)

    original_filename = _normalize_filename(file.filename)
    browser_content_type = _normalize_content_type(file.content_type)
    original_extension = _extract_extension(original_filename)

    _validate_filename(original_filename)

    file_bytes = await read_upload_bytes(file)
    max_size_bytes = _get_max_size_for_purpose(purpose)

    _validate_size(file_bytes, max_size_bytes=max_size_bytes)

    detected_content_type, width_px, height_px = _detect_image_metadata(file_bytes)

    if (
        browser_content_type is not None
        and browser_content_type != detected_content_type
    ):
        raise MediaValidationError(
            "Uploaded file content type does not match the actual image type.",
            code="content_type_mismatch",
        )

    _validate_content_type_allowed(detected_content_type)
    _validate_extension_matches_content_type(
        extension=original_extension,
        content_type=detected_content_type,
    )
    _validate_dimensions(
        purpose=purpose,
        width_px=width_px,
        height_px=height_px,
    )

    extension = _get_effective_extension(
        original_extension=original_extension,
        detected_content_type=detected_content_type,
    )

    return ValidatedMediaFile(
        original_filename=original_filename,
        content_type=detected_content_type,
        extension=extension,
        size_bytes=len(file_bytes),
        checksum_sha256=_calculate_sha256(file_bytes),
        width_px=width_px,
        height_px=height_px,
        data=file_bytes,
    )


async def validate_school_logo_upload(file: UploadFile) -> ValidatedMediaFile:
    """Validate a school logo upload."""

    return await validate_uploaded_image(
        file=file,
        purpose=MediaPurpose.SCHOOL_LOGO,
    )


async def validate_student_passport_upload(file: UploadFile) -> ValidatedMediaFile:
    """Validate a student passport upload."""

    return await validate_uploaded_image(
        file=file,
        purpose=MediaPurpose.STUDENT_PASSPORT,
    )


async def validate_teacher_passport_upload(file: UploadFile) -> ValidatedMediaFile:
    """Validate a teacher passport upload."""

    return await validate_uploaded_image(
        file=file,
        purpose=MediaPurpose.TEACHER_PASSPORT,
    )


async def validate_tenant_admin_passport_upload(file: UploadFile) -> ValidatedMediaFile:
    """Validate a tenant admin passport upload."""

    return await validate_uploaded_image(
        file=file,
        purpose=MediaPurpose.TENANT_ADMIN_PASSPORT,
    )
