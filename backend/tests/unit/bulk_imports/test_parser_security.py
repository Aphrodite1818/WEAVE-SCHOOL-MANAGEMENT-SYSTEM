from __future__ import annotations

import io
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.core.exceptions import ImportParserError
from app.modules.bulk_imports.parsers import _validate_xlsx_archive


def _archive_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_xlsx_archive_rejects_path_traversal() -> None:
    file_bytes = _archive_bytes({"../outside.xml": b"unsafe"})

    with pytest.raises(ImportParserError, match="unsafe internal path"):
        _validate_xlsx_archive(file_bytes)


def test_xlsx_archive_rejects_suspicious_compression_ratio() -> None:
    file_bytes = _archive_bytes({"xl/worksheets/sheet1.xml": b"A" * 1_000_000})

    with pytest.raises(ImportParserError, match="suspicious compression ratio"):
        _validate_xlsx_archive(file_bytes)


def test_xlsx_archive_accepts_small_normal_container() -> None:
    file_bytes = _archive_bytes(
        {
            "[Content_Types].xml": b"<Types />",
            "xl/workbook.xml": b"<workbook />",
        }
    )

    _validate_xlsx_archive(file_bytes)
