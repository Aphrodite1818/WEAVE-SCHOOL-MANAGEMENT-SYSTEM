"""Protect and selectively reveal sensitive bulk-import result values."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import settings


SETUP_CODE_FIELD = "setup_code"
SETUP_CODE_CIPHERTEXT_FIELD = "setup_code_ciphertext"
SETUP_CODE_PROTECTED_AT_FIELD = "setup_code_protected_at"
SETUP_CODE_AVAILABLE_UNTIL_FIELD = "setup_code_available_until"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fernet() -> Fernet:
    source = settings.BULK_IMPORT_RESULT_ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def protect_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with any plaintext setup code encrypted."""

    protected = dict(row)
    setup_code = protected.pop(SETUP_CODE_FIELD, None)
    if setup_code in {None, ""}:
        return protected

    now = _utc_now()
    protected[SETUP_CODE_CIPHERTEXT_FIELD] = _fernet().encrypt(
        str(setup_code).encode("utf-8")
    ).decode("ascii")
    protected[SETUP_CODE_PROTECTED_AT_FIELD] = now.isoformat()
    protected[SETUP_CODE_AVAILABLE_UNTIL_FIELD] = (
        now + timedelta(hours=settings.BULK_IMPORT_SETUP_CODE_RETENTION_HOURS)
    ).isoformat()
    return protected


def protect_import_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Encrypt setup codes before import metadata reaches PostgreSQL."""

    if metadata is None:
        return None
    protected = deepcopy(metadata)
    result_rows = protected.get("result_rows")
    if isinstance(result_rows, list):
        protected["result_rows"] = [
            protect_result_row(row) if isinstance(row, dict) else row
            for row in result_rows
        ]
    return protected


def reveal_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with a non-expired setup code decrypted for slip generation."""

    revealed = dict(row)
    plaintext = revealed.get(SETUP_CODE_FIELD)
    if plaintext not in {None, ""}:
        return revealed

    ciphertext = revealed.get(SETUP_CODE_CIPHERTEXT_FIELD)
    available_until = _parse_datetime(revealed.get(SETUP_CODE_AVAILABLE_UNTIL_FIELD))
    if not ciphertext or (available_until is not None and available_until <= _utc_now()):
        revealed.pop(SETUP_CODE_FIELD, None)
        return revealed

    try:
        revealed[SETUP_CODE_FIELD] = _fernet().decrypt(
            str(ciphertext).encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        revealed.pop(SETUP_CODE_FIELD, None)
    return revealed


def redact_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove setup-code material from normal API and spreadsheet responses."""

    redacted = dict(row)
    available_until = _parse_datetime(redacted.get(SETUP_CODE_AVAILABLE_UNTIL_FIELD))
    redacted["setup_code_available"] = bool(
        redacted.get(SETUP_CODE_CIPHERTEXT_FIELD)
        and (available_until is None or available_until > _utc_now())
    )
    for field in (
        SETUP_CODE_FIELD,
        SETUP_CODE_CIPHERTEXT_FIELD,
        SETUP_CODE_PROTECTED_AT_FIELD,
        SETUP_CODE_AVAILABLE_UNTIL_FIELD,
    ):
        redacted.pop(field, None)
    return redacted


def sanitize_import_metadata_for_response(
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Remove sensitive setup-code fields from job-detail responses."""

    if metadata is None:
        return None
    sanitized = deepcopy(metadata)
    result_rows = sanitized.get("result_rows")
    if isinstance(result_rows, list):
        sanitized["result_rows"] = [
            redact_result_row(row) if isinstance(row, dict) else row
            for row in result_rows
        ]
    return sanitized
