# ========================== #
#   bulk_imports_parsers.py  #
# ========================== #

"""File parsers for tenant bulk import uploads."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from fastapi import UploadFile
from openpyxl import load_workbook

from app.core.exceptions import ImportParserError
from app.modules.bulk_imports.models import ImportFileType


MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5_000


@dataclass(frozen=True)
class ParsedImportRow:
    """One parsed row from an uploaded import file."""

    row_number: int
    raw_data: dict[str, Any]


def _decode_csv_bytes(file_bytes: bytes) -> str:
    """Decode CSV bytes using common encodings."""

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ImportParserError("Unable to decode CSV file.")


def _clean_headers(headers: Sequence[Any]) -> list[str]:
    """Normalize parser-level headers by trimming whitespace."""

    cleaned_headers: list[str] = []

    for header in headers:
        if header is None:
            cleaned_headers.append("")
            continue

        cleaned_headers.append(str(header).strip())

    return cleaned_headers


def _ensure_unique_headers(headers: list[str]) -> None:
    """Reject duplicate non-empty headers."""

    seen_headers: set[str] = set()

    for header in headers:
        if not header:
            continue

        normalized_header = header.strip().lower()

        if normalized_header in seen_headers:
            raise ImportParserError(f"Duplicate column header found: {header}")

        seen_headers.add(normalized_header)


def _is_blank_row(row_data: dict[str, Any]) -> bool:
    """Return True when all row values are blank."""

    return all(value is None or str(value).strip() == "" for value in row_data.values())


def _to_serializable_value(value: Any) -> Any:
    """Convert spreadsheet values into JSON-safe values."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        cleaned_value = value.strip()
        return cleaned_value or None

    return value


def _build_row_from_values(
    *,
    headers: list[str],
    values: Sequence[Any],
) -> dict[str, Any]:
    """Build one raw row dictionary from headers and row values."""

    return {
        headers[index]: _to_serializable_value(value)
        for index, value in enumerate(values)
        if index < len(headers) and headers[index]
    }


class BulkImportParser:
    """Parse uploaded CSV/XLSX files into row dictionaries."""

    @staticmethod
    def resolve_file_type(
        *,
        filename: str | None,
        file_type: ImportFileType | None = None,
    ) -> ImportFileType:
        """Resolve file type from explicit input or filename extension."""

        if file_type is not None:
            return file_type

        if not filename:
            raise ImportParserError("Uploaded file must have a filename.")

        extension = Path(filename).suffix.lower().lstrip(".")

        if extension == ImportFileType.CSV.value:
            return ImportFileType.CSV

        if extension == ImportFileType.XLSX.value:
            return ImportFileType.XLSX

        raise ImportParserError("Only CSV and XLSX files are supported.")

    @staticmethod
    def parse_csv_bytes(
        *,
        file_bytes: bytes,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> list[ParsedImportRow]:
        """Parse CSV bytes into row dictionaries."""

        text = _decode_csv_bytes(file_bytes)
        stream = io.StringIO(text)
        reader = csv.reader(stream)

        try:
            header_row = next(reader)
        except StopIteration as exc:
            raise ImportParserError("CSV file is empty.") from exc

        headers = _clean_headers(header_row)

        if not any(headers):
            raise ImportParserError("CSV file must contain at least one valid column header.")

        _ensure_unique_headers(headers)

        rows: list[ParsedImportRow] = []

        for row_number, row_values in enumerate(reader, start=2):
            raw_data = _build_row_from_values(headers=headers, values=row_values)

            if _is_blank_row(raw_data):
                continue

            rows.append(
                ParsedImportRow(
                    row_number=row_number,
                    raw_data=raw_data,
                )
            )

            if len(rows) > max_rows:
                raise ImportParserError(f"Import file cannot exceed {max_rows} data rows.")

        return rows

    @staticmethod
    def parse_xlsx_bytes(
        *,
        file_bytes: bytes,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> list[ParsedImportRow]:
        """Parse XLSX bytes into row dictionaries."""

        workbook = load_workbook(
            filename=io.BytesIO(file_bytes),
            read_only=True,
            data_only=True,
        )
        worksheet = workbook.active

        if worksheet is None:
            raise ImportParserError("Workbook has no active worksheet.")

        rows_iter = worksheet.iter_rows(values_only=True)

        try:
            header_row = next(rows_iter)
        except StopIteration as exc:
            raise ImportParserError("XLSX file is empty.") from exc

        headers = _clean_headers(header_row)

        if not any(headers):
            raise ImportParserError("XLSX file must contain at least one valid column header.")

        _ensure_unique_headers(headers)

        parsed_rows: list[ParsedImportRow] = []

        for row_number, row_values in enumerate(rows_iter, start=2):
            raw_data = _build_row_from_values(headers=headers, values=row_values)

            if _is_blank_row(raw_data):
                continue

            parsed_rows.append(
                ParsedImportRow(
                    row_number=row_number,
                    raw_data=raw_data,
                )
            )

            if len(parsed_rows) > max_rows:
                raise ImportParserError(f"Import file cannot exceed {max_rows} data rows.")

        return parsed_rows

    @staticmethod
    async def parse_upload(
        upload_file: UploadFile,
        *,
        file_type: ImportFileType | None = None,
        max_file_size_bytes: int = MAX_IMPORT_FILE_SIZE_BYTES,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> tuple[ImportFileType, int, list[ParsedImportRow]]:
        """Read an uploaded file and return parsed rows with file metadata."""

        file_bytes = await upload_file.read()

        if not file_bytes:
            raise ImportParserError("Uploaded file is empty.")

        file_size_bytes = len(file_bytes)

        if file_size_bytes > max_file_size_bytes:
            raise ImportParserError(
                f"Uploaded file is too large. Maximum allowed size is {max_file_size_bytes} bytes."
            )

        resolved_file_type = BulkImportParser.resolve_file_type(
            filename=upload_file.filename,
            file_type=file_type,
        )

        if resolved_file_type == ImportFileType.CSV:
            rows = BulkImportParser.parse_csv_bytes(
                file_bytes=file_bytes,
                max_rows=max_rows,
            )
            return resolved_file_type, file_size_bytes, rows

        if resolved_file_type == ImportFileType.XLSX:
            rows = BulkImportParser.parse_xlsx_bytes(
                file_bytes=file_bytes,
                max_rows=max_rows,
            )
            return resolved_file_type, file_size_bytes, rows

        raise ImportParserError("Unsupported import file type.")
