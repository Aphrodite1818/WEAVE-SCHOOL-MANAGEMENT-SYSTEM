# ============================= #
#   bulk_imports_result_writer.py #
# ============================= #

"""Result file writers for tenant bulk import workflows."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.modules.bulk_imports.models import ImportResourceType


@dataclass(frozen=True)
class ImportResultFile:
    """Generated import result file."""

    filename: str
    content_type: str
    content_bytes: bytes


class ImportResultWriterError(ValueError):
    """Raised when an import result file cannot be generated."""


def create_result_filename(
    *,
    resource_type: ImportResourceType,
    suffix: str,
) -> str:
    """Create a timestamped result filename."""

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
    writer = csv.DictWriter(
        output,
        fieldnames=headers,
        extrasaction="ignore",
    )

    writer.writeheader()

    for row in rows:
        csv_row = {
            header: convert_value_for_csv(row.get(header))
            for header in headers
        }
        writer.writerow(csv_row)

    return output.getvalue().encode("utf-8-sig")


def build_error_report_rows(
    *,
    row_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build CSV rows for failed import rows."""

    report_rows: list[dict[str, Any]] = []

    for row_error in row_errors:
        normalized_row = row_error.get("normalized_row") or {}
        raw_row = row_error.get("raw_row") or {}

        report_row = {
            "row_number": row_error.get("row_number"),
            "field_name": row_error.get("field_name"),
            "error_code": row_error.get("error_code"),
            "error_message": row_error.get("error_message"),
        }

        if isinstance(raw_row, dict):
            for key, value in raw_row.items():
                report_row[f"raw_{key}"] = value

        if isinstance(normalized_row, dict):
            for key, value in normalized_row.items():
                report_row[f"normalized_{key}"] = value

        report_rows.append(report_row)

    return report_rows


def build_summary_report_rows(
    *,
    resource_type: ImportResourceType,
    total_rows: int,
    successful_rows: int,
    failed_rows: int,
    skipped_rows: int,
    status: str,
) -> list[dict[str, Any]]:
    """Build CSV rows for import summary data."""

    return [
        {
            "resource_type": resource_type.value,
            "status": status,
            "total_rows": total_rows,
            "successful_rows": successful_rows,
            "failed_rows": failed_rows,
            "skipped_rows": skipped_rows,
        }
    ]


def create_empty_error_report(
    *,
    resource_type: ImportResourceType,
) -> ImportResultFile:
    """Create an empty error report."""

    filename = create_result_filename(
        resource_type=resource_type,
        suffix="errors",
    )

    headers = [
        "row_number",
        "field_name",
        "error_code",
        "error_message",
    ]

    content_bytes = write_csv_bytes(
        rows=[],
        headers=headers,
    )

    return ImportResultFile(
        filename=filename,
        content_type="text/csv",
        content_bytes=content_bytes,
    )


def create_error_report(
    *,
    resource_type: ImportResourceType,
    row_errors: list[dict[str, Any]],
) -> ImportResultFile:
    """Create a CSV error report for failed rows."""

    if not row_errors:
        return create_empty_error_report(resource_type=resource_type)

    report_rows = build_error_report_rows(row_errors=row_errors)

    preferred_headers = [
        "row_number",
        "field_name",
        "error_code",
        "error_message",
    ]

    headers = collect_csv_headers(
        rows=report_rows,
        preferred_headers=preferred_headers,
    )

    content_bytes = write_csv_bytes(
        rows=report_rows,
        headers=headers,
    )

    filename = create_result_filename(
        resource_type=resource_type,
        suffix="errors",
    )

    return ImportResultFile(
        filename=filename,
        content_type="text/csv",
        content_bytes=content_bytes,
    )


def create_summary_report(
    *,
    resource_type: ImportResourceType,
    total_rows: int,
    successful_rows: int,
    failed_rows: int,
    skipped_rows: int,
    status: str,
) -> ImportResultFile:
    """Create a CSV summary report for an import job."""

    report_rows = build_summary_report_rows(
        resource_type=resource_type,
        total_rows=total_rows,
        successful_rows=successful_rows,
        failed_rows=failed_rows,
        skipped_rows=skipped_rows,
        status=status,
    )

    headers = [
        "resource_type",
        "status",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "skipped_rows",
    ]

    content_bytes = write_csv_bytes(
        rows=report_rows,
        headers=headers,
    )

    filename = create_result_filename(
        resource_type=resource_type,
        suffix="summary",
    )

    return ImportResultFile(
        filename=filename,
        content_type="text/csv",
        content_bytes=content_bytes,
    )