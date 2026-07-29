from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.bulk_imports.sensitive_results import (
    protect_import_metadata,
    redact_result_row,
    reveal_result_row,
    sanitize_import_metadata_for_response,
)


def test_setup_codes_are_encrypted_before_metadata_persistence() -> None:
    protected = protect_import_metadata(
        {
            "result_rows": [
                {
                    "row_number": 2,
                    "status": "created",
                    "admission_number": "STU-001",
                    "setup_code": "12345678",
                    "access_code_expires_at": (
                        datetime.now(timezone.utc) + timedelta(hours=48)
                    ).isoformat(),
                }
            ]
        }
    )

    row = protected["result_rows"][0]
    assert "setup_code" not in row
    assert row["setup_code_ciphertext"]
    assert row["setup_code_ciphertext"] != "12345678"


def test_authorized_slip_path_can_reveal_non_expired_setup_code() -> None:
    protected = protect_import_metadata(
        {
            "result_rows": [
                {
                    "row_number": 2,
                    "status": "created",
                    "setup_code": "12345678",
                    "access_code_expires_at": (
                        datetime.now(timezone.utc) + timedelta(hours=48)
                    ).isoformat(),
                }
            ]
        }
    )

    revealed = reveal_result_row(protected["result_rows"][0])
    assert revealed["setup_code"] == "12345678"


def test_expired_encrypted_setup_code_is_not_revealed() -> None:
    protected = protect_import_metadata(
        {"result_rows": [{"row_number": 2, "status": "created", "setup_code": "12345678"}]}
    )
    row = protected["result_rows"][0]
    row["setup_code_available_until"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()

    revealed = reveal_result_row(row)
    assert "setup_code" not in revealed


def test_expired_legacy_plaintext_setup_code_is_not_revealed() -> None:
    row = {
        "row_number": 2,
        "status": "created",
        "setup_code": "12345678",
        "access_code_expires_at": (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat(),
    }

    revealed = reveal_result_row(row)
    assert "setup_code" not in revealed
    assert redact_result_row(row)["setup_code_available"] is False


def test_normal_responses_redact_plaintext_and_ciphertext() -> None:
    protected = protect_import_metadata(
        {"result_rows": [{"row_number": 2, "status": "created", "setup_code": "12345678"}]}
    )

    sanitized = sanitize_import_metadata_for_response(protected)
    row = sanitized["result_rows"][0]
    assert "setup_code" not in row
    assert "setup_code_ciphertext" not in row
    assert row["setup_code_available"] is True

    redacted = redact_result_row(protected["result_rows"][0])
    assert "setup_code" not in redacted
    assert "setup_code_ciphertext" not in redacted
