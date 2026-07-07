# ================================ #
#   bulk_imports_result_writer.py  #
# ================================ #

"""Result file writers for tenant bulk import workflows."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.modules.bulk_imports.models import ImportResourceType


@dataclass(frozen=True)
class ImportResultFile:
    """Generated import result file."""

    filename: str
    content_type: str
    content_bytes: bytes


def create_result_filename(
    *,
    resource_type: ImportResourceType,
    suffix: str,
) -> str:
    """Create a timestamped result filename."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{resource_type.value}_{suffix}_{timestamp}.csv"


def collect_csv_headers(
    *,
    rows: list[dict[str, Any]],
    preferred_headers: list[str] | None = None,
) -> list[str]:
    """Collect stable CSV headers from row dictionaries."""

    headers: list[str] = []

    for header in preferred_headers or []:
        if header not in headers:
            headers.append(header)

    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    return headers


def convert_value_for_csv(value: Any) -> str:
    """Convert a Python value into a CSV-safe string."""

    if value is None:
        return ""

    if isinstance(value, dict | list):
        return str(value)

    return str(value)


def write_csv_bytes(
    *,
    rows: list[dict[str, Any]],
    headers: list[str],
) -> bytes:
    """Write rows to CSV bytes."""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                header: convert_value_for_csv(row.get(header))
                for header in headers
            }
        )

    return output.getvalue().encode("utf-8-sig")


def create_result_report(
    *,
    resource_type: ImportResourceType,
    result_rows: list[dict[str, Any]],
) -> ImportResultFile:
    """Create a CSV report containing successful and failed row outcomes."""

    preferred_headers_by_resource = {
        ImportResourceType.STUDENTS: [
            "row_number",
            "status",
            "first_name",
            "last_name",
            "admission_number",
            "setup_code",
            "access_code_expires_at",
            "error_message",
        ],
        ImportResourceType.TEACHERS: [
            "row_number",
            "status",
            "invite_status",
            "email",
            "first_name",
            "last_name",
            "staff_id",
            "error_message",
        ],
        ImportResourceType.PARENTS: [
            "row_number",
            "status",
            "invite_status",
            "email",
            "first_name",
            "last_name",
            "error_message",
        ],
    }

    headers = collect_csv_headers(
        rows=result_rows,
        preferred_headers=preferred_headers_by_resource.get(resource_type, []),
    )

    if not headers:
        headers = ["row_number", "status", "error_message"]

    return ImportResultFile(
        filename=create_result_filename(resource_type=resource_type, suffix="result"),
        content_type="text/csv",
        content_bytes=write_csv_bytes(rows=result_rows, headers=headers),
    )


def create_error_report(
    *,
    resource_type: ImportResourceType,
    row_errors: list[dict[str, Any]],
) -> ImportResultFile:
    """Create a CSV report containing only row errors."""

    headers = collect_csv_headers(
        rows=row_errors,
        preferred_headers=[
            "row_number",
            "field_name",
            "error_code",
            "error_message",
        ],
    )

    return ImportResultFile(
        filename=create_result_filename(resource_type=resource_type, suffix="errors"),
        content_type="text/csv",
        content_bytes=write_csv_bytes(rows=row_errors, headers=headers),
    )
