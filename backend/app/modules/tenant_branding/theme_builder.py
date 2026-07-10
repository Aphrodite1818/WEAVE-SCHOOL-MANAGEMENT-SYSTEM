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
DEFAULT_HEADER_COLOR: Final[str] = "#F8FAFC"
DEFAULT_BACKGROUND_COLOR: Final[str] = "#F8FAFC"
DEFAULT_DARK_HEADER_COLOR: Final[str] = "#0A0F1C"
DEFAULT_DARK_BACKGROUND_COLOR: Final[str] = "#0A0F1C"

LIGHT_TEXT_RGB: Final[tuple[int, int, int]] = (255, 255, 255)
DARK_TEXT_RGB: Final[tuple[int, int, int]] = (15, 23, 42)
LIGHT_THEME_MUTED_TEXT_RGB: Final[tuple[int, int, int]] = (100, 116, 139)
DARK_THEME_MUTED_TEXT_RGB: Final[tuple[int, int, int]] = (148, 163, 184)

REQUIRED_THEME_TOKEN_KEYS: Final[set[str]] = {
    "--color-primary",
    "--color-primary-hover",
    "--color-primary-soft",
    "--color-primary-subtle",
    "--color-primary-deep",
    "--color-accent",
    "--color-accent-hover",
    "--color-accent-soft",
    "--color-workspace-background",
    "--color-header-background",
    "--color-header-text",
    "--color-header-text-muted",
    "--color-header-surface",
    "--color-header-surface-hover",
    "--color-header-border",
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
    "--color-workspace-background": "248 250 252",
    "--color-header-background": "248 250 252",
    "--color-header-text": "15 23 42",
    "--color-header-text-muted": "100 116 139",
    "--color-header-surface": "255 255 255",
    "--color-header-surface-hover": "241 245 249",
    "--color-header-border": "226 232 240",
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


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB tuple into an uppercase hex color."""

    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def channels_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert `R G B` channel notation into an RGB tuple."""

    try:
        red_text, green_text, blue_text = str(value).strip().split()
        rgb = (int(red_text), int(green_text), int(blue_text))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid RGB channel token: {value!r}.") from exc

    if any(channel < 0 or channel > 255 for channel in rgb):
        raise ValueError(f"RGB channel values must be between 0 and 255: {value!r}.")

    return rgb


def channels_to_hex(value: str) -> str:
    """Convert `R G B` channel notation into an uppercase hex color."""

    return rgb_to_hex(channels_to_rgb(value))


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


def choose_readable_text_color(
    background_rgb: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Choose a readable text color for a background."""

    white_contrast = _contrast_ratio(background_rgb, LIGHT_TEXT_RGB)
    dark_contrast = _contrast_ratio(background_rgb, DARK_TEXT_RGB)
    return LIGHT_TEXT_RGB if white_contrast >= dark_contrast else DARK_TEXT_RGB


def choose_readable_sidebar_text_color(
    sidebar_rgb: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Choose a readable text color for the sidebar background."""

    return choose_readable_text_color(sidebar_rgb)


def get_default_header_color(theme_mode: TenantBrandingThemeMode) -> str:
    """Return the safe default header color for a theme mode."""

    if theme_mode == TenantBrandingThemeMode.DARK:
        return DEFAULT_DARK_HEADER_COLOR
    return DEFAULT_HEADER_COLOR


def get_default_background_color(theme_mode: TenantBrandingThemeMode) -> str:
    """Return the safe default workspace background color for a theme mode."""

    if theme_mode == TenantBrandingThemeMode.DARK:
        return DEFAULT_DARK_BACKGROUND_COLOR
    return DEFAULT_BACKGROUND_COLOR


def build_theme_tokens(
    *,
    primary_color: str,
    accent_color: str,
    sidebar_color: str,
    theme_mode: TenantBrandingThemeMode,
    header_color: str | None = None,
    background_color: str | None = None,
) -> dict[str, str]:
    """Build safe theme tokens from simple admin-controlled branding values."""

    normalized_primary = normalize_hex_color(primary_color)
    normalized_accent = normalize_hex_color(accent_color)
    normalized_sidebar = normalize_hex_color(sidebar_color)
    normalized_header = normalize_hex_color(header_color or get_default_header_color(theme_mode))
    normalized_background = normalize_hex_color(
        background_color or get_default_background_color(theme_mode)
    )

    if (
        normalized_primary == DEFAULT_PRIMARY_COLOR
        and normalized_accent == DEFAULT_ACCENT_COLOR
        and normalized_sidebar == DEFAULT_SIDEBAR_COLOR
        and theme_mode == DEFAULT_THEME_MODE
        and normalized_header == DEFAULT_HEADER_COLOR
        and normalized_background == DEFAULT_BACKGROUND_COLOR
    ):
        return dict(DEFAULT_THEME_TOKENS)

    primary_rgb = hex_to_rgb(normalized_primary)
    accent_rgb = hex_to_rgb(normalized_accent)
    sidebar_rgb = hex_to_rgb(normalized_sidebar)
    header_rgb = hex_to_rgb(normalized_header)
    background_rgb = hex_to_rgb(normalized_background)

    primary_hover_rgb = _adjust_lightness(primary_rgb, -0.12)
    primary_soft_rgb = _blend_towards(primary_rgb, LIGHT_TEXT_RGB, 0.84)
    primary_subtle_rgb = _blend_towards(primary_rgb, LIGHT_TEXT_RGB, 0.92)
    primary_deep_rgb = _adjust_lightness(primary_rgb, -0.22)

    accent_hover_rgb = _adjust_lightness(accent_rgb, -0.10)
    accent_soft_rgb = _blend_towards(accent_rgb, LIGHT_TEXT_RGB, 0.80)

    sidebar_text_rgb = choose_readable_sidebar_text_color(sidebar_rgb)
    header_text_rgb = choose_readable_text_color(header_rgb)
    default_muted_header_text_rgb = (
        DARK_THEME_MUTED_TEXT_RGB if header_text_rgb == LIGHT_TEXT_RGB else LIGHT_THEME_MUTED_TEXT_RGB
    )
    header_text_muted_rgb = _blend_towards(default_muted_header_text_rgb, header_rgb, 0.16)
    header_surface_rgb = _blend_towards(header_rgb, header_text_rgb, 0.08)
    header_surface_hover_rgb = _blend_towards(header_rgb, header_text_rgb, 0.14)
    header_border_rgb = _blend_towards(header_rgb, header_text_rgb, 0.18)

    return {
        "--color-primary": rgb_to_channels(primary_rgb),
        "--color-primary-hover": rgb_to_channels(primary_hover_rgb),
        "--color-primary-soft": rgb_to_channels(primary_soft_rgb),
        "--color-primary-subtle": rgb_to_channels(primary_subtle_rgb),
        "--color-primary-deep": rgb_to_channels(primary_deep_rgb),
        "--color-accent": rgb_to_channels(accent_rgb),
        "--color-accent-hover": rgb_to_channels(accent_hover_rgb),
        "--color-accent-soft": rgb_to_channels(accent_soft_rgb),
        "--color-workspace-background": rgb_to_channels(background_rgb),
        "--color-header-background": rgb_to_channels(header_rgb),
        "--color-header-text": rgb_to_channels(header_text_rgb),
        "--color-header-text-muted": rgb_to_channels(header_text_muted_rgb),
        "--color-header-surface": rgb_to_channels(header_surface_rgb),
        "--color-header-surface-hover": rgb_to_channels(header_surface_hover_rgb),
        "--color-header-border": rgb_to_channels(header_border_rgb),
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
