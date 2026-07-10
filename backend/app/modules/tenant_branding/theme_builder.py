"""Helpers for building safe tenant branding theme tokens."""

from __future__ import annotations

import colorsys
import re
from typing import Final

from app.modules.tenant_branding.models import TenantBrandingThemeMode


DEFAULT_BRAND_NAME: Final[str] = "Learnly AI"
DEFAULT_PRIMARY_COLOR: Final[str] = "#2563EB"
DEFAULT_ACCENT_COLOR: Final[str] = "#4F46E5"
DEFAULT_SIDEBAR_COLOR: Final[str] = "#0F172A"
DEFAULT_THEME_MODE: Final[TenantBrandingThemeMode] = TenantBrandingThemeMode.LIGHT

LIGHT_TEXT_RGB: Final[tuple[int, int, int]] = (255, 255, 255)
DARK_TEXT_RGB: Final[tuple[int, int, int]] = (15, 23, 42)

REQUIRED_THEME_TOKEN_KEYS: Final[set[str]] = {
    "--color-primary",
    "--color-primary-hover",
    "--color-primary-soft",
    "--color-primary-subtle",
    "--color-primary-deep",
    "--color-accent",
    "--color-accent-hover",
    "--color-accent-soft",
    "--color-sidebar-background",
    "--color-sidebar-text",
}

DEFAULT_THEME_TOKENS: Final[dict[str, str]] = {
    "--color-primary": "37 99 235",
    "--color-primary-hover": "29 78 216",
    "--color-primary-soft": "219 234 254",
    "--color-primary-subtle": "239 246 255",
    "--color-primary-deep": "30 58 138",
    "--color-accent": "79 70 229",
    "--color-accent-hover": "67 56 202",
    "--color-accent-soft": "224 231 255",
    "--color-sidebar-background": "15 23 42",
    "--color-sidebar-text": "255 255 255",
}

HEX_COLOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^#?(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex_color(value: str) -> str:
    """Validate a hex color and normalize it to uppercase `#RRGGBB`."""

    if value is None:
        raise ValueError("Color value is required.")

    cleaned_value = str(value).strip()
    if not HEX_COLOR_PATTERN.fullmatch(cleaned_value):
        raise ValueError(f"Invalid hex color: {value!r}.")

    normalized = cleaned_value.lstrip("#").upper()
    if len(normalized) == 3:
        normalized = "".join(character * 2 for character in normalized)

    return f"#{normalized}"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a hex color into an RGB tuple."""

    normalized = normalize_hex_color(value).lstrip("#")
    return tuple(int(normalized[index:index + 2], 16) for index in (0, 2, 4))


def rgb_to_channels(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB tuple into `R G B` channel notation."""

    return f"{rgb[0]} {rgb[1]} {rgb[2]}"


def _clamp_channel(value: float) -> int:
    """Clamp a computed color channel into the valid RGB range."""

    return max(0, min(255, int(round(value))))


def _adjust_lightness(rgb: tuple[int, int, int], delta: float) -> tuple[int, int, int]:
    """Adjust color lightness using HLS so derived tokens stay visually related."""

    red, green, blue = (channel / 255 for channel in rgb)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    next_lightness = min(1.0, max(0.0, lightness + delta))
    next_red, next_green, next_blue = colorsys.hls_to_rgb(hue, next_lightness, saturation)
    return (
        _clamp_channel(next_red * 255),
        _clamp_channel(next_green * 255),
        _clamp_channel(next_blue * 255),
    )


def _blend_towards(
    source: tuple[int, int, int],
    target: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    """Blend an RGB color towards another RGB color."""

    return tuple(
        _clamp_channel(source[index] + (target[index] - source[index]) * ratio)
        for index in range(3)
    )


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate WCAG relative luminance for a color."""

    def transform(channel: int) -> float:
        normalized = channel / 255
        if normalized <= 0.03928:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    red, green, blue = (transform(channel) for channel in rgb)
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _contrast_ratio(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    """Return WCAG contrast ratio between two RGB colors."""

    left_luminance = _relative_luminance(left)
    right_luminance = _relative_luminance(right)
    lighter = max(left_luminance, right_luminance)
    darker = min(left_luminance, right_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def choose_readable_sidebar_text_color(
    sidebar_rgb: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Choose a readable text color for the sidebar background."""

    white_contrast = _contrast_ratio(sidebar_rgb, LIGHT_TEXT_RGB)
    dark_contrast = _contrast_ratio(sidebar_rgb, DARK_TEXT_RGB)
    return LIGHT_TEXT_RGB if white_contrast >= dark_contrast else DARK_TEXT_RGB


def build_theme_tokens(
    *,
    primary_color: str,
    accent_color: str,
    sidebar_color: str,
    theme_mode: TenantBrandingThemeMode,
) -> dict[str, str]:
    """Build safe theme tokens from simple admin-controlled branding values."""

    normalized_primary = normalize_hex_color(primary_color)
    normalized_accent = normalize_hex_color(accent_color)
    normalized_sidebar = normalize_hex_color(sidebar_color)

    if (
        normalized_primary == DEFAULT_PRIMARY_COLOR
        and normalized_accent == DEFAULT_ACCENT_COLOR
        and normalized_sidebar == DEFAULT_SIDEBAR_COLOR
        and theme_mode == DEFAULT_THEME_MODE
    ):
        return dict(DEFAULT_THEME_TOKENS)

    primary_rgb = hex_to_rgb(normalized_primary)
    accent_rgb = hex_to_rgb(normalized_accent)
    sidebar_rgb = hex_to_rgb(normalized_sidebar)

    primary_hover_rgb = _adjust_lightness(primary_rgb, -0.12)
    primary_soft_rgb = _blend_towards(primary_rgb, LIGHT_TEXT_RGB, 0.84)
    primary_subtle_rgb = _blend_towards(primary_rgb, LIGHT_TEXT_RGB, 0.92)
    primary_deep_rgb = _adjust_lightness(primary_rgb, -0.22)

    accent_hover_rgb = _adjust_lightness(accent_rgb, -0.10)
    accent_soft_rgb = _blend_towards(accent_rgb, LIGHT_TEXT_RGB, 0.80)

    sidebar_text_rgb = choose_readable_sidebar_text_color(sidebar_rgb)

    return {
        "--color-primary": rgb_to_channels(primary_rgb),
        "--color-primary-hover": rgb_to_channels(primary_hover_rgb),
        "--color-primary-soft": rgb_to_channels(primary_soft_rgb),
        "--color-primary-subtle": rgb_to_channels(primary_subtle_rgb),
        "--color-primary-deep": rgb_to_channels(primary_deep_rgb),
        "--color-accent": rgb_to_channels(accent_rgb),
        "--color-accent-hover": rgb_to_channels(accent_hover_rgb),
        "--color-accent-soft": rgb_to_channels(accent_soft_rgb),
        "--color-sidebar-background": rgb_to_channels(sidebar_rgb),
        "--color-sidebar-text": rgb_to_channels(sidebar_text_rgb),
    }


def build_default_theme_tokens() -> dict[str, str]:
    """Return the default Learnly tenant theme tokens."""

    return dict(DEFAULT_THEME_TOKENS)


def is_complete_theme_token_set(tokens: dict[str, str] | None) -> bool:
    """Return whether a token dictionary includes every required tenant theme token."""

    if not tokens:
        return False

    return REQUIRED_THEME_TOKEN_KEYS.issubset(tokens.keys())
