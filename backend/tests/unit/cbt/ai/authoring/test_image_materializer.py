from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from unittest.mock import AsyncMock, call

import pytest
from PIL import Image

from app.modules.cbt.ai.authoring.image_materializer import (
    ImageDownloadError,
    ImageMaterializer,
    InvalidImageError,
)
from app.modules.cbt.ai.authoring.providers.base import ImageCandidate, ProviderGeneratedImage


def _encoded_image(format_name: str = "PNG") -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (32, 24), "white")
    image.save(buffer, format=format_name)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_transport_round_trip_preserves_encoded_file_bytes() -> None:
    raw = _encoded_image("PNG")
    digest = hashlib.sha256(raw).hexdigest()
    materializer = ImageMaterializer()

    image = await materializer.materialize_transport_base64(
        data_base64=base64.b64encode(raw).decode("ascii"),
        content_type="image/png",
        expected_sha256=digest,
        label="existing_question.image",
    )

    assert image.data == raw
    assert image.sha256 == digest
    assert image.content_type == "image/png"
    assert image.width == 32
    assert image.height == 24
    assert image.label == "existing_question.image"
    assert base64.b64decode(materializer.encode_transport_base64(image)) == raw


@pytest.mark.asyncio
async def test_transport_rejects_mime_type_that_does_not_match_bytes() -> None:
    raw = _encoded_image("PNG")
    with pytest.raises(InvalidImageError, match="content type"):
        await ImageMaterializer().materialize_transport_base64(
            data_base64=base64.b64encode(raw).decode("ascii"),
            content_type="image/jpeg",
            expected_sha256=hashlib.sha256(raw).hexdigest(),
        )


@pytest.mark.asyncio
async def test_transport_rejects_hash_mismatch() -> None:
    raw = _encoded_image("PNG")
    with pytest.raises(InvalidImageError, match="SHA-256"):
        await ImageMaterializer().materialize_transport_base64(
            data_base64=base64.b64encode(raw).decode("ascii"),
            content_type="image/png",
            expected_sha256="0" * 64,
        )


@pytest.mark.asyncio
async def test_generated_base64_is_materialized_to_real_image_file_bytes() -> None:
    raw = _encoded_image("PNG")
    image = await ImageMaterializer().materialize_generated(
        ProviderGeneratedImage(
            content_type="image/png",
            data_base64=base64.b64encode(raw).decode("ascii"),
        )
    )

    assert image.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert image.content_type == "image/png"
    assert hashlib.sha256(image.data).hexdigest() == image.sha256


@pytest.mark.asyncio
async def test_candidate_falls_back_to_thumbnail_when_original_url_is_unusable() -> None:
    raw = _encoded_image("PNG")
    materializer = ImageMaterializer()
    materializer._download = AsyncMock(
        side_effect=[
            ImageDownloadError("original unavailable"),
            raw,
        ]
    )
    candidate = ImageCandidate(
        source="openverse",
        source_url="https://example.com/source",
        image_url="https://cdn.example.com/original.png",
        thumbnail_url="https://cdn.example.com/thumbnail.png",
        mime_type="image/png",
    )

    image = await materializer.materialize_candidate(candidate)

    assert image.content_type == "image/png"
    assert materializer._download.await_args_list == [
        call("https://cdn.example.com/original.png"),
        call("https://cdn.example.com/thumbnail.png"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/image.png",
        "http://localhost/image.png",
    ],
)
async def test_external_image_url_rejects_non_public_targets(url: str) -> None:
    with pytest.raises(ImageDownloadError):
        await ImageMaterializer._validate_public_url(url)
