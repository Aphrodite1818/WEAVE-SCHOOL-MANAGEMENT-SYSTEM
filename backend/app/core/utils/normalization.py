# ====================================== #
#        core/utils/normalization.py      #
# ====================================== #

"""Shared canonicalization helpers for backend-owned identifiers.

These helpers separate human-facing display values from normalized values used
for lookups, uniqueness checks, imports, and duplicate prevention.
"""

from __future__ import annotations

import re
from typing import Any

_CLASS_PREFIX_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^J\.?S\.?S\.?\s*[-_]?\s*(\d+)$", re.IGNORECASE), "JSS"),
    (re.compile(r"^JUNIOR\s+SECONDARY\s*[-_]?\s*(\d+)$", re.IGNORECASE), "JSS"),
    (re.compile(r"^S\.?S\.?S\.?\s*[-_]?\s*(\d+)$", re.IGNORECASE), "SS"),
    (re.compile(r"^S\.?S\.?\s*[-_]?\s*(\d+)$", re.IGNORECASE), "SS"),
    (re.compile(r"^SENIOR\s+SECONDARY\s*[-_]?\s*(\d+)$", re.IGNORECASE), "SS"),
    (re.compile(r"^PRIMARY\s*[-_]?\s*(\d+)$", re.IGNORECASE), "PRIMARY"),
    (re.compile(r"^PRY\s*[-_]?\s*(\d+)$", re.IGNORECASE), "PRIMARY"),
    (re.compile(r"^BASIC\s*[-_]?\s*(\d+)$", re.IGNORECASE), "BASIC"),
    (re.compile(r"^NURSERY\s*[-_]?\s*(\d+)$", re.IGNORECASE), "NURSERY"),
    (re.compile(r"^KG\s*[-_]?\s*(\d+)$", re.IGNORECASE), "KG"),
)

_CLASS_FULL_NAME_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"^JUNIOR\s*SECONDARY\s*SCHOOL\s*[-_]?\s*(\d+)$",
            re.IGNORECASE,
        ),
        "JUNIOR SECONDARY SCHOOL",
    ),
    (
        re.compile(
            r"^SENIOR\s*SECONDARY\s*SCHOOL\s*[-_]?\s*(\d+)$",
            re.IGNORECASE,
        ),
        "SENIOR SECONDARY SCHOOL",
    ),
)

_NO_ARM_SENTINELS = {"-", "NOARM", "NO_ARM", "NO ARM", "NONE", "N/A", "NA"}


def clean_string(value: Any) -> str | None:
    """Trim and collapse whitespace; return None for blank values."""

    if value is None:
        return None

    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def normalize_display_text(value: Any) -> str | None:
    """Clean generic display text without changing semantic casing."""

    return clean_string(value)


def normalize_title_text(value: Any) -> str | None:
    """Clean generic human names/labels and title-case them for display."""

    cleaned = clean_string(value)
    return cleaned.title() if cleaned else None


def normalize_email(value: Any) -> str | None:
    """Normalize email values for storage and lookup."""

    cleaned = clean_string(value)
    return cleaned.lower() if cleaned else None


def normalize_phone(value: Any) -> str | None:
    """Normalize phone-like values by removing whitespace only."""

    cleaned = clean_string(value)
    if cleaned is None:
        return None
    return re.sub(r"\s+", "", cleaned)


def normalize_code(value: Any) -> str | None:
    """Normalize short business identifiers by removing spaces and uppercasing."""

    cleaned = clean_string(value)
    if cleaned is None:
        return None
    normalized = re.sub(r"\s+", "", cleaned).upper()
    return normalized or None


def normalize_staff_id(value: Any) -> str | None:
    """Normalize teacher/staff identifiers."""

    return normalize_code(value)


def normalize_admission_number(value: Any) -> str | None:
    """Normalize student admission numbers."""

    return normalize_code(value)


def normalize_school_prefix(value: Any) -> str | None:
    """Normalize school admission-number prefixes."""

    return normalize_code(value)


def normalize_grade(value: Any) -> str | None:
    """Normalize grading scale labels such as a, a+, b2."""

    return normalize_code(value)


def normalize_subject_code(value: Any) -> str | None:
    """Normalize subject codes."""

    return normalize_code(value)


def normalize_subject_name(value: Any) -> str | None:
    """Normalize subject names for duplicate prevention."""

    cleaned = clean_string(value)
    return cleaned.casefold() if cleaned else None


def _display_class_name(value: Any) -> str | None:
    """Return a readable canonical class name for display."""

    cleaned = clean_string(value)
    if cleaned is None:
        return None

    compact = re.sub(r"[\s_\-]+", " ", cleaned).strip()

    for pattern, label in _CLASS_FULL_NAME_ALIASES:
        match = pattern.fullmatch(compact)
        if match:
            return f"{label} {match.group(1)}"

    for pattern, prefix in _CLASS_PREFIX_ALIASES:
        match = pattern.fullmatch(compact)
        if match:
            return f"{prefix}{match.group(1)}"

    alphanumeric_only = re.sub(r"[^A-Za-z0-9]+", "", compact)
    if alphanumeric_only:
        return alphanumeric_only.upper()

    return compact.upper()


def normalize_class_name(value: Any) -> str | None:
    """Normalize a classroom name for display and canonical lookup.

    Examples:
    - jss1, JSS 1, JSS-1 -> JSS1
    - ss 2, SSS2 -> SS2
    - primary 4, pry4 -> PRIMARY4
    """

    return _display_class_name(value)


def normalized_class_name_key(value: Any) -> str | None:
    """Normalize a classroom name for uniqueness and lookup keys."""

    normalized = _display_class_name(value)
    if normalized is None:
        return None
    return re.sub(r"[^A-Za-z0-9]+", "", normalized).upper()


def normalize_class_arm(value: Any) -> str | None:
    """Normalize a class arm for display; blank arms are allowed."""

    cleaned = clean_string(value)
    if cleaned is None:
        return None

    normalized = re.sub(r"\s+", "", cleaned).upper()
    if normalized in _NO_ARM_SENTINELS:
        return None

    return normalized or None


def normalized_class_arm_key(value: Any) -> str:
    """Normalize a class arm for uniqueness and lookup keys.

    Empty string represents the canonical no-arm class.
    """

    normalized = normalize_class_arm(value)
    return normalized or ""
