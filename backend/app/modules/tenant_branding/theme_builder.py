"""Helpers for building safe tenant branding theme tokens."""

from __future__ import annotations

import colorsys
import re
from typing import Final

from app.modules.tenant_branding.models import TenantBrandingThemeMode


DEFAULT_BRAND_NAME: Final[str] = "Weave"
DEFAULT_PRIMARY_COLOR: Final[str] = "#1D4ED8"
DEFAULT_ACCENT_COLOR: Final[str] = "#4F46E5"
DEFAULT_SIDEBAR_COLOR: Final[str] = "#FFFFFF"
DEFAULT_THEME_MODE: Final[TenantBrandingThemeMode] = TenantBrandingThemeMode.LIGHT
DEFAULT_HEADER_COLOR: Final[str] = "#FFFFFF"
DEFAULT_BACKGROUND_COLOR: Final[str] = "#F8FAFC"
DEFAULT_DARK_HEADER_COLOR: Final[str] = "#0A0F1C"
DEFAULT_DARK_BACKGROUND_COLOR: Final[str] = "#0A0F1C"

LIGHT_TEXT_RGB: Final[tuple[int, int, int]] = (255, 255, 255)
DARK_TEXT_RGB: Final[tuple[int, int, int]] = (15, 23, 42)
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


# Versioned semantic contract used by workspace clients. Legacy flat token
# payloads are treated as stale and regenerated from the stored source palette.
TOKEN_SCHEMA_VERSION: Final[int] = 1
DEFAULT_SURFACE_COLOR: Final[str] = "#FFFFFF"
SEMANTIC_THEME_TOKEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "--color-primary", "--color-primary-hover", "--color-primary-soft",
        "--color-primary-subtle", "--color-primary-deep", "--color-on-primary",
        "--color-accent", "--color-accent-hover", "--color-accent-soft",
        "--color-on-accent", "--color-background", "--color-surface",
        "--color-surface-raised", "--color-surface-muted", "--color-surface-subtle",
        "--color-border", "--color-border-strong", "--color-border-subtle",
        "--color-text", "--color-text-soft", "--color-text-muted",
        "--color-text-faint", "--color-text-inverse", "--color-sidebar-background",
        "--color-sidebar-text", "--color-sidebar-active", "--color-sidebar-active-text",
        "--color-sidebar-border", "--color-header-background", "--color-header-text",
        "--color-header-text-muted", "--color-header-surface",
        "--color-header-surface-hover", "--color-header-border", "--color-focus-ring",
    }
)


def _semantic_tokens(
    *,
    primary: tuple[int, int, int],
    accent: tuple[int, int, int],
    sidebar: tuple[int, int, int],
    header: tuple[int, int, int],
    background: tuple[int, int, int],
    surface: tuple[int, int, int],
    dark: bool,
) -> dict[str, str]:
    canvas = _blend_towards(background, DARK_TEXT_RGB, 0.88) if dark else background
    card = _blend_towards(surface, DARK_TEXT_RGB, 0.86) if dark else surface
    contrast_target = LIGHT_TEXT_RGB if dark else DARK_TEXT_RGB
    text = (248, 250, 252) if dark else DARK_TEXT_RGB
    side = _blend_towards(sidebar, DARK_TEXT_RGB, 0.78) if dark else sidebar
    head = _blend_towards(header, DARK_TEXT_RGB, 0.84) if dark else header
    side_text = choose_readable_text_color(side)
    head_text = choose_readable_text_color(head)
    values = {
        "--color-primary": primary,
        "--color-primary-hover": _adjust_lightness(primary, 0.08 if dark else -0.08),
        "--color-primary-soft": _blend_towards(primary, card, 0.84),
        "--color-primary-subtle": _blend_towards(primary, card, 0.92),
        "--color-primary-deep": _adjust_lightness(primary, -0.18),
        "--color-on-primary": choose_readable_text_color(primary),
        "--color-accent": accent,
        "--color-accent-hover": _adjust_lightness(accent, 0.08 if dark else -0.08),
        "--color-accent-soft": _blend_towards(accent, card, 0.80),
        "--color-on-accent": choose_readable_text_color(accent),
        "--color-background": canvas,
        "--color-surface": card,
        "--color-surface-raised": _blend_towards(card, LIGHT_TEXT_RGB, 0.05 if dark else 0),
        "--color-surface-muted": _blend_towards(card, contrast_target, 0.08),
        "--color-surface-subtle": _blend_towards(card, contrast_target, 0.15),
        "--color-border": _blend_towards(card, contrast_target, 0.18 if dark else 0.12),
        "--color-border-strong": _blend_towards(card, contrast_target, 0.28 if dark else 0.20),
        "--color-border-subtle": _blend_towards(card, contrast_target, 0.10 if dark else 0.06),
        "--color-text": text,
        "--color-text-soft": (226, 232, 240) if dark else (51, 65, 85),
        "--color-text-muted": (148, 163, 184) if dark else (100, 116, 139),
        "--color-text-faint": (100, 116, 139) if dark else (148, 163, 184),
        "--color-text-inverse": LIGHT_TEXT_RGB,
        "--color-sidebar-background": side,
        "--color-sidebar-text": side_text,
        "--color-sidebar-active": primary,
        "--color-sidebar-active-text": choose_readable_text_color(primary),
        "--color-sidebar-border": _blend_towards(side, side_text, 0.16),
        "--color-header-background": head,
        "--color-header-text": head_text,
        "--color-header-text-muted": _blend_towards(head_text, head, 0.35),
        "--color-header-surface": _blend_towards(head, head_text, 0.08),
        "--color-header-surface-hover": _blend_towards(head, head_text, 0.14),
        "--color-header-border": _blend_towards(head, head_text, 0.18),
        "--color-focus-ring": primary,
    }
    return {key: rgb_to_channels(value) for key, value in values.items()}


def build_theme_token_sets(
    *, primary_color: str, accent_color: str, sidebar_color: str,
    header_color: str, background_color: str, surface_color: str,
) -> dict[str, dict[str, str]]:
    values = {
        "primary": hex_to_rgb(primary_color), "accent": hex_to_rgb(accent_color),
        "sidebar": hex_to_rgb(sidebar_color), "header": hex_to_rgb(header_color),
        "background": hex_to_rgb(background_color), "surface": hex_to_rgb(surface_color),
    }
    return {
        "light": _semantic_tokens(**values, dark=False),
        "dark": _semantic_tokens(**values, dark=True),
    }


def build_default_theme_token_sets() -> dict[str, dict[str, str]]:
    """Return defaults matching the existing Weave light and dark workspaces."""

    light = build_theme_token_sets(
        primary_color="#1D4ED8", accent_color=DEFAULT_ACCENT_COLOR,
        sidebar_color="#FFFFFF", header_color="#FFFFFF",
        background_color="#F8FAFC", surface_color=DEFAULT_SURFACE_COLOR,
    )["light"]
    light.update({
        "--color-primary-hover": "30 64 175", "--color-primary-soft": "219 234 254",
        "--color-primary-subtle": "239 246 255", "--color-primary-deep": "30 58 138",
        "--color-accent-hover": "67 56 202", "--color-accent-soft": "224 231 255",
        "--color-surface-muted": "241 245 249", "--color-surface-subtle": "226 232 240",
        "--color-border": "226 232 240", "--color-border-strong": "203 213 225",
        "--color-border-subtle": "241 245 249", "--color-sidebar-text": "51 65 85",
        "--color-sidebar-border": "226 232 240", "--color-header-text-muted": "100 116 139",
        "--color-header-surface-hover": "241 245 249", "--color-header-border": "226 232 240",
    })
    dark = dict(light)
    dark.update({
        "--color-background": "10 15 28", "--color-surface": "15 23 42",
        "--color-surface-raised": "20 31 54", "--color-surface-muted": "30 41 59",
        "--color-surface-subtle": "51 65 85", "--color-border": "51 65 85",
        "--color-border-strong": "71 85 105", "--color-border-subtle": "30 41 59",
        "--color-text": "248 250 252", "--color-text-soft": "226 232 240",
        "--color-text-muted": "148 163 184", "--color-text-faint": "100 116 139",
        "--color-sidebar-background": "15 23 42", "--color-sidebar-text": "226 232 240",
        "--color-sidebar-border": "51 65 85", "--color-header-background": "15 23 42",
        "--color-header-text": "248 250 252", "--color-header-text-muted": "148 163 184",
        "--color-header-surface": "20 31 54", "--color-header-surface-hover": "30 41 59",
        "--color-header-border": "51 65 85",
    })
    return {"light": light, "dark": dark}


def is_current_token_payload(tokens: object, schema_version: int | None) -> bool:
    return (
        schema_version == TOKEN_SCHEMA_VERSION
        and isinstance(tokens, dict)
        and isinstance(tokens.get("light"), dict)
        and isinstance(tokens.get("dark"), dict)
        and SEMANTIC_THEME_TOKEN_KEYS.issubset(tokens["light"])
        and SEMANTIC_THEME_TOKEN_KEYS.issubset(tokens["dark"])
    )
