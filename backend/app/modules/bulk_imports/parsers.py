# ========================== #
#   bulk_imports_parsers.py  #
# ========================== #

"""File parsers for tenant bulk import uploads."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from fastapi import UploadFile
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.core.exceptions import ImportParserError
from app.modules.bulk_imports.models import ImportFileType
from app.modules.bulk_imports.templates import CONTROL_COLUMNS, TEMPLATE_METADATA_SHEET_NAME


MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5_000


@dataclass(frozen=True)
class ParsedImportRow:
    """One parsed row from an uploaded import file."""

    row_number: int
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class ParsedImportFile:
    """Parsed import file plus file-level metadata."""

    file_type: ImportFileType
    file_size_bytes: int
    headers: list[str]
    rows: list[ParsedImportRow]
    metadata: dict[str, Any] = field(default_factory=dict)


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


def _normalize_header_key(header: Any) -> str:
    """Normalize a header key for metadata/control column detection."""

    return str(header or "").strip().lower()


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


def _data_headers_from_headers(headers: list[str]) -> list[str]:
    """Return data headers with signed template control columns removed."""

    return [
        header
        for header in headers
        if _normalize_header_key(header) not in CONTROL_COLUMNS
    ]


def _extract_csv_metadata(rows: list[ParsedImportRow]) -> dict[str, Any]:
    """Extract visible control-column metadata from the first CSV data row."""

    if not rows:
        return {}

    first_row = rows[0].raw_data
    metadata: dict[str, Any] = {}

    for key, value in first_row.items():
        normalized_key = _normalize_header_key(key)
        if normalized_key in CONTROL_COLUMNS:
            metadata[normalized_key] = value

    return metadata


def _read_xlsx_metadata(workbook) -> dict[str, Any]:
    """Read template metadata from the hidden XLSX metadata sheet."""

    if TEMPLATE_METADATA_SHEET_NAME not in workbook.sheetnames:
        return {}

    worksheet = workbook[TEMPLATE_METADATA_SHEET_NAME]
    metadata: dict[str, Any] = {}

    for row in worksheet.iter_rows(values_only=True):
        if not row or len(row) < 2:
            continue

        key = _to_serializable_value(row[0])
        value = _to_serializable_value(row[1])

        if not key or str(key).strip().lower() == "key":
            continue

        metadata[str(key).strip()] = value

    return metadata


def _select_xlsx_data_sheet(workbook) -> Worksheet:
    """Select the first visible non-metadata worksheet as the import data sheet."""

    for worksheet in workbook.worksheets:
        if worksheet.title == TEMPLATE_METADATA_SHEET_NAME:
            continue

        if getattr(worksheet, "sheet_state", "visible") == "visible":
            return worksheet

    raise ImportParserError("XLSX file must contain a visible import data sheet.")


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
        file_size_bytes: int,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> ParsedImportFile:
        """Parse CSV bytes into a parsed import file."""

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

        return ParsedImportFile(
            file_type=ImportFileType.CSV,
            file_size_bytes=file_size_bytes,
            headers=_data_headers_from_headers(headers),
            rows=rows,
            metadata=_extract_csv_metadata(rows),
        )

    @staticmethod
    def parse_xlsx_bytes(
        *,
        file_bytes: bytes,
        file_size_bytes: int,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> ParsedImportFile:
        """Parse XLSX bytes into a parsed import file."""

        workbook = load_workbook(
            filename=io.BytesIO(file_bytes),
            read_only=False,
            data_only=True,
        )
        worksheet = _select_xlsx_data_sheet(workbook)
        metadata = _read_xlsx_metadata(workbook)

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

        return ParsedImportFile(
            file_type=ImportFileType.XLSX,
            file_size_bytes=file_size_bytes,
            headers=headers,
            rows=parsed_rows,
            metadata=metadata,
        )

    @staticmethod
    async def parse_upload(
        upload_file: UploadFile,
        *,
        file_type: ImportFileType | None = None,
        max_file_size_bytes: int = MAX_IMPORT_FILE_SIZE_BYTES,
        max_rows: int = MAX_IMPORT_ROWS,
    ) -> ParsedImportFile:
        """Read an uploaded file and return parsed file metadata and rows."""

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
            return BulkImportParser.parse_csv_bytes(
                file_bytes=file_bytes,
                file_size_bytes=file_size_bytes,
                max_rows=max_rows,
            )

        if resolved_file_type == ImportFileType.XLSX:
            return BulkImportParser.parse_xlsx_bytes(
                file_bytes=file_bytes,
                file_size_bytes=file_size_bytes,
                max_rows=max_rows,
            )

        raise ImportParserError("Unsupported import file type.")
