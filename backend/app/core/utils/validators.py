# ======================================#
#            validators.py             #
# ======================================#
"""Reusable helpers for validating and normalizing application data."""

import re


def generate_slug(school_name: str) -> str:
    """Convert a school name into a URL-friendly slug."""
    slug = school_name.lower()

    slug = re.sub(r"[^\w\s-]", "", slug)  # remove special chars [^] not in

    slug = re.sub(
        r"[\s_]+", "-", slug
    )  # spaces or underscores → hyphens + means one or more char in a row

    slug = re.sub(r"-+", "-", slug)  # collapse multiple hyphens

    return slug.strip("-")


def validate_password_strength(password: str) -> None:
    """Enforce a minimum password baseline for first-login password changes."""

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if password.lower() == password or password.upper() == password:
        raise ValueError("Password must include both uppercase and lowercase letters")

    if not re.search(r"\d", password):
        raise ValueError("Password must include at least one number")


SESSION_NAME_PATTERN = re.compile(r"^\d{4}/\d{4}$")


def validate_academic_session_name(value: str) -> str:
    value = value.strip()

    if not SESSION_NAME_PATTERN.fullmatch(value):
        raise ValueError("Academic session must use the format YYYY/YYYY, e.g. 2026/2027.")

    start_year_str, end_year_str = value.split("/")
    start_year = int(start_year_str)
    end_year = int(end_year_str)

    if end_year != start_year + 1:
        raise ValueError("Academic session end year must be exactly one year after start year.")

    return value
