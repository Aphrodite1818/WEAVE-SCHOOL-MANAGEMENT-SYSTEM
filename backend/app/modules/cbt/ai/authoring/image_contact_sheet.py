"""Build compact numbered contact sheets for CBT image evaluation."""

from __future__ import annotations

import hashlib
import math
import warnings
from io import BytesIO
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.modules.cbt.ai.authoring.providers.base import ProviderImageInput


CONTACT_SHEET_LABEL_PREFIX = "candidate_contact_sheet:"
MAX_CONTACT_SHEET_CANDIDATES = 12
CONTACT_SHEET_COLUMNS = 4
TILE_WIDTH = 320
TILE_HEIGHT = 240
LABEL_HEIGHT = 36
PADDING = 8


def contact_sheet_candidate_count(images: Sequence[ProviderImageInput]) -> int | None:
    """Return the candidate count encoded by one contact-sheet image."""

    if len(images) != 1:
        return None
    label = images[0].label or ""
    if not label.startswith(CONTACT_SHEET_LABEL_PREFIX):
        return None
    raw_count = label.removeprefix(CONTACT_SHEET_LABEL_PREFIX)
    try:
        count = int(raw_count)
    except ValueError:
        return None
    if not 1 <= count <= MAX_CONTACT_SHEET_CANDIDATES:
        return None
    return count


def build_candidate_contact_sheet(
    images: Sequence[ProviderImageInput],
) -> ProviderImageInput:
    """Combine candidate previews into one numbered JPEG contact sheet.

    Candidate labels use zero-based indices so the visual labels map directly to
    ProviderImageEvaluationResult.selected_index without another translation.
    """

    if not images:
        raise ValueError("At least one candidate image is required for a contact sheet.")
    if len(images) > MAX_CONTACT_SHEET_CANDIDATES:
        raise ValueError(
            f"Contact sheets support at most {MAX_CONTACT_SHEET_CANDIDATES} candidates."
        )

    count = len(images)
    columns = min(CONTACT_SHEET_COLUMNS, count)
    rows = math.ceil(count / columns)
    tile_outer_height = LABEL_HEIGHT + TILE_HEIGHT
    width = PADDING + columns * (TILE_WIDTH + PADDING)
    height = PADDING + rows * (tile_outer_height + PADDING)

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = _load_label_font()

    for index, provider_image in enumerate(images):
        row, column = divmod(index, columns)
        x = PADDING + column * (TILE_WIDTH + PADDING)
        y = PADDING + row * (tile_outer_height + PADDING)

        draw.rectangle(
            (x, y, x + TILE_WIDTH - 1, y + LABEL_HEIGHT - 1),
            fill=(235, 235, 235),
            outline=(80, 80, 80),
            width=1,
        )
        draw.text(
            (x + 10, y + 5),
            f"#{index}",
            fill=(0, 0, 0),
            font=font,
        )

        preview = _decode_preview(provider_image)
        contained = ImageOps.contain(
            preview,
            (TILE_WIDTH, TILE_HEIGHT),
            method=Image.Resampling.LANCZOS,
        )
        tile = Image.new("RGB", (TILE_WIDTH, TILE_HEIGHT), "white")
        paste_x = (TILE_WIDTH - contained.width) // 2
        paste_y = (TILE_HEIGHT - contained.height) // 2
        tile.paste(contained, (paste_x, paste_y))
        sheet.paste(tile, (x, y + LABEL_HEIGHT))
        draw.rectangle(
            (x, y + LABEL_HEIGHT, x + TILE_WIDTH - 1, y + tile_outer_height - 1),
            outline=(80, 80, 80),
            width=1,
        )

    output = BytesIO()
    sheet.save(
        output,
        format="JPEG",
        quality=82,
        optimize=True,
        progressive=True,
    )
    encoded = output.getvalue()

    return ProviderImageInput(
        data=encoded,
        content_type="image/jpeg",
        sha256=hashlib.sha256(encoded).hexdigest(),
        width=sheet.width,
        height=sheet.height,
        label=f"{CONTACT_SHEET_LABEL_PREFIX}{count}",
        alt_text=(
            f"Numbered contact sheet containing {count} image candidates labelled "
            f"#0 through #{count - 1}."
        ),
    )


def _decode_preview(image: ProviderImageInput) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image.data)) as opened:
                opened.seek(0)
                preview = ImageOps.exif_transpose(opened)
                preview.load()
                return preview.convert("RGB")
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ValueError("Candidate preview is not a valid supported image.") from exc


def _load_label_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, 24)
        except OSError:
            continue
    return ImageFont.load_default()
