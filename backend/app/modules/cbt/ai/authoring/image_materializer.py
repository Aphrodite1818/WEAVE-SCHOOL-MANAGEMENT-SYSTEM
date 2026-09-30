"""Safe image materialization for CBT AI authoring.

External URLs and provider Base64 are transient inputs only. A successful
materialization always returns validated encoded image-file bytes using the
provider-agnostic ProviderImageInput contract.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import ipaddress
import socket
import warnings
from io import BytesIO
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.cbt.ai.authoring.providers.base import (
    ImageCandidate,
    ProviderGeneratedImage,
    ProviderImageInput,
)


class ImageMaterializationError(RuntimeError):
    """Raised when an image cannot be safely materialized and normalized."""


class ImageDownloadError(ImageMaterializationError):
    """Raised when an external image URL cannot be safely downloaded."""


class InvalidImageError(ImageMaterializationError):
    """Raised when supplied bytes are not a supported, safe image."""


class ImageMaterializer:
    """Download/decode, validate, normalize and fingerprint image assets."""

    MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
    MAX_NORMALIZED_BYTES = 5 * 1024 * 1024
    MAX_PIXELS = 16_000_000
    MAX_DIMENSION = 8_192
    TARGET_MAX_DIMENSION = 2_048
    MAX_REDIRECTS = 3
    DOWNLOAD_TIMEOUT_SECONDS = 12.0

    ALLOWED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
    TRANSPORT_FORMATS = {"JPEG", "PNG", "WEBP"}
    MIME_BY_FORMAT = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }

    async def materialize_candidate(
        self,
        candidate: ImageCandidate,
        *,
        label: str | None = None,
    ) -> ProviderImageInput:
        """Download and normalize one searched image candidate."""

        url = candidate.image_url or candidate.thumbnail_url
        if not url:
            raise ImageDownloadError("Image candidate contains no downloadable URL.")

        image_bytes = await self._download(url)
        return await asyncio.to_thread(
            self._normalize_bytes,
            image_bytes,
            candidate.mime_type,
            label,
            candidate.title,
        )

    async def materialize_generated(
        self,
        image: ProviderGeneratedImage,
        *,
        label: str | None = None,
    ) -> ProviderImageInput:
        """Materialize provider output whether it arrived as Base64 or a URL."""

        if image.data_base64:
            raw = self._decode_base64(image.data_base64)
        elif image.url:
            raw = await self._download(image.url)
        else:
            raise ImageMaterializationError(
                "Image provider returned neither image data nor a downloadable URL."
            )

        return await asyncio.to_thread(
            self._normalize_bytes,
            raw,
            image.content_type,
            label,
            image.alt_text,
        )

    async def materialize_transport_base64(
        self,
        *,
        data_base64: str,
        content_type: str,
        expected_sha256: str | None = None,
        label: str | None = None,
        alt_text: str | None = None,
    ) -> ProviderImageInput:
        """Decode/validate CBT transport data while preserving encoded bytes.

        Images already crossed the application boundary as complete encoded
        files. Re-encoding them here would repeatedly recompress JPEG/WebP on
        regeneration, so this path verifies the image and keeps its bytes intact.
        """

        raw = self._decode_base64(data_base64)
        if len(raw) > self.MAX_NORMALIZED_BYTES:
            raise InvalidImageError("CBT image payload exceeds the maximum allowed size.")

        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if (
            expected_sha256 is not None
            and actual_sha256.casefold() != expected_sha256.casefold()
        ):
            raise InvalidImageError("Image SHA-256 does not match the supplied payload.")

        return await asyncio.to_thread(
            self._validate_transport_bytes,
            raw,
            content_type,
            actual_sha256,
            label,
            alt_text,
        )

    @classmethod
    def encode_transport_base64(cls, image: ProviderImageInput) -> str:
        """Encode canonical image bytes for JSON transport to the local CBT."""

        return base64.b64encode(image.data).decode("ascii")

    @classmethod
    def _decode_base64(cls, value: str) -> bytes:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError, TypeError) as exc:
            raise InvalidImageError("Image payload contains invalid Base64 data.") from exc

        if not decoded:
            raise InvalidImageError("Image payload is empty.")
        if len(decoded) > cls.MAX_DOWNLOAD_BYTES:
            raise InvalidImageError("Image payload exceeds the maximum allowed size.")
        return decoded

    async def _download(self, initial_url: str) -> bytes:
        """Download one public HTTP(S) image with redirect and size controls."""

        current_url = initial_url
        async with httpx.AsyncClient(
            timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            for redirect_count in range(self.MAX_REDIRECTS + 1):
                await self._validate_public_url(current_url)
                try:
                    async with client.stream("GET", current_url) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise ImageDownloadError(
                                    "Image server returned a redirect without a location."
                                )
                            if redirect_count >= self.MAX_REDIRECTS:
                                raise ImageDownloadError("Image download exceeded redirect limit.")
                            current_url = urljoin(current_url, location)
                            continue

                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length:
                            try:
                                declared_size = int(content_length)
                            except ValueError:
                                declared_size = 0
                            if declared_size > self.MAX_DOWNLOAD_BYTES:
                                raise ImageDownloadError(
                                    "Image download exceeds the maximum allowed size."
                                )

                        chunks: list[bytes] = []
                        total = 0
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > self.MAX_DOWNLOAD_BYTES:
                                raise ImageDownloadError(
                                    "Image download exceeds the maximum allowed size."
                                )
                            chunks.append(chunk)

                        payload = b"".join(chunks)
                        if not payload:
                            raise ImageDownloadError("Downloaded image is empty.")
                        return payload
                except ImageDownloadError:
                    raise
                except httpx.TimeoutException as exc:
                    raise ImageDownloadError("Image download timed out.") from exc
                except httpx.HTTPError as exc:
                    raise ImageDownloadError("Unable to download image.") from exc

        raise ImageDownloadError("Unable to download image.")

    @staticmethod
    async def _validate_public_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ImageDownloadError("Only HTTP(S) image URLs are supported.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise ImageDownloadError("Image URL is not permitted.")

        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise ImageDownloadError("Image hostname could not be resolved.") from exc

        if not addresses:
            raise ImageDownloadError("Image hostname resolved to no addresses.")

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ImageDownloadError("Image URL resolves to a non-public network address.")

    @classmethod
    def _validate_transport_bytes(
        cls,
        raw: bytes,
        hinted_content_type: str,
        sha256: str,
        label: str | None,
        alt_text: str | None,
    ) -> ProviderImageInput:
        """Validate an already-encoded CBT image without recompressing it."""

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as image:
                    image_format = (image.format or "").upper()
                    width, height = image.size
                    if image_format not in cls.TRANSPORT_FORMATS:
                        raise InvalidImageError("Unsupported CBT transport image format.")
                    cls._validate_dimensions(width, height)
                    image.verify()
        except InvalidImageError:
            raise
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise InvalidImageError("Payload is not a valid supported image.") from exc

        actual_content_type = cls.MIME_BY_FORMAT[image_format]
        if hinted_content_type.casefold() != actual_content_type:
            raise InvalidImageError("Image content type does not match the encoded image bytes.")

        return ProviderImageInput(
            data=raw,
            content_type=actual_content_type,
            sha256=sha256,
            width=width,
            height=height,
            label=label,
            alt_text=alt_text,
        )

    @classmethod
    def _normalize_bytes(
        cls,
        raw: bytes,
        hinted_content_type: str | None,
        label: str | None,
        alt_text: str | None,
    ) -> ProviderImageInput:
        """Validate real image bytes and return an efficiently encoded file image."""

        _ = hinted_content_type  # Never trust MIME metadata over decoded image content.

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as probe:
                    image_format = (probe.format or "").upper()
                    width, height = probe.size
                    if image_format not in cls.ALLOWED_INPUT_FORMATS:
                        raise InvalidImageError("Unsupported image format.")
                    cls._validate_dimensions(width, height)
                    probe.verify()

                with Image.open(BytesIO(raw)) as opened:
                    opened.seek(0)
                    image = ImageOps.exif_transpose(opened)
                    image.load()
                    image_format = (opened.format or image_format).upper()
                    image = cls._resize_if_needed(image)
                    encoded, content_type = cls._encode_normalized(image, image_format)
        except InvalidImageError:
            raise
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise InvalidImageError("Payload is not a valid supported image.") from exc

        if len(encoded) > cls.MAX_NORMALIZED_BYTES:
            encoded, content_type = cls._encode_webp(image, quality=82)
        if len(encoded) > cls.MAX_NORMALIZED_BYTES:
            raise InvalidImageError("Normalized image exceeds the maximum allowed size.")

        width, height = image.size
        return ProviderImageInput(
            data=encoded,
            content_type=content_type,
            sha256=hashlib.sha256(encoded).hexdigest(),
            width=width,
            height=height,
            label=label,
            alt_text=alt_text,
        )

    @classmethod
    def _validate_dimensions(cls, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise InvalidImageError("Image has invalid dimensions.")
        if width > cls.MAX_DIMENSION or height > cls.MAX_DIMENSION:
            raise InvalidImageError("Image dimensions exceed the maximum allowed size.")
        if width * height > cls.MAX_PIXELS:
            raise InvalidImageError("Image pixel count exceeds the maximum allowed size.")

    @classmethod
    def _resize_if_needed(cls, image: Image.Image) -> Image.Image:
        width, height = image.size
        max_dimension = max(width, height)
        if max_dimension <= cls.TARGET_MAX_DIMENSION:
            return image.copy()

        scale = cls.TARGET_MAX_DIMENSION / max_dimension
        target = (max(1, round(width * scale)), max(1, round(height * scale)))
        return image.resize(target, Image.Resampling.LANCZOS)

    @classmethod
    def _encode_normalized(cls, image: Image.Image, original_format: str) -> tuple[bytes, str]:
        output = BytesIO()

        if original_format == "JPEG":
            image.convert("RGB").save(
                output,
                format="JPEG",
                quality=88,
                optimize=True,
                progressive=True,
            )
            return output.getvalue(), "image/jpeg"

        if original_format == "WEBP":
            prepared = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            prepared.save(output, format="WEBP", quality=88, method=4)
            return output.getvalue(), "image/webp"

        if original_format == "PNG":
            prepared = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            prepared.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"

        # GIFs are intentionally flattened to the first frame for CBT assets.
        prepared = image.convert("RGBA")
        prepared.save(output, format="WEBP", lossless=True, method=4)
        return output.getvalue(), "image/webp"

    @staticmethod
    def _encode_webp(image: Image.Image, *, quality: int) -> tuple[bytes, str]:
        output = BytesIO()
        prepared = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
        prepared.save(output, format="WEBP", quality=quality, method=4)
        return output.getvalue(), "image/webp"
