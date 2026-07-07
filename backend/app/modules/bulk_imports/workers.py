# ========================= #
#   bulk_imports_workers.py #
# ========================= #

"""Worker helpers for tenant bulk import processing.

This file does not contain resource-specific business logic.
The service layer should provide the function that processes each row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.modules.bulk_imports.chunking import ImportChunk, chunk_import_items


RowProcessor = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ImportWorkerResult:
    """Result from processing a batch of normalized import rows."""

    processed_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    row_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ImportWorkerRow:
    """One row passed into the worker."""

    row_number: int
    normalized_row: dict[str, Any]


class BulkImportWorkerError(RuntimeError):
    """Raised when worker processing fails unexpectedly."""


def create_worker_row(
    *,
    row_number: int,
    normalized_row: dict[str, Any],
) -> ImportWorkerRow:
    """Create one worker row item."""

    return ImportWorkerRow(
        row_number=row_number,
        normalized_row=normalized_row,
    )


def create_row_error_data(
    *,
    row_number: int,
    normalized_row: dict[str, Any],
    error_message: str,
    error_code: str = "processing_error",
    field_name: str | None = None,
) -> dict[str, Any]:
    """Create a serializable row error dictionary."""

    return {
        "row_number": row_number,
        "field_name": field_name,
        "error_code": error_code,
        "error_message": error_message,
        "normalized_row": normalized_row,
    }


async def process_worker_row(
    *,
    worker_row: ImportWorkerRow,
    row_processor: RowProcessor,
) -> dict[str, Any] | None:
    """Process one normalized row.

    Returns None when the row succeeds.
    Returns an error dictionary when the row fails.
    """

    try:
        await row_processor(worker_row.normalized_row)
    except Exception as exc:
        return create_row_error_data(
            row_number=worker_row.row_number,
            normalized_row=worker_row.normalized_row,
            error_message=str(exc),
        )

    return None


async def process_worker_chunk(
    *,
    chunk: ImportChunk[ImportWorkerRow],
    row_processor: RowProcessor,
) -> ImportWorkerResult:
    """Process one chunk of normalized rows."""

    result = ImportWorkerResult()

    for worker_row in chunk.items:
        result.processed_rows += 1

        row_error = await process_worker_row(
            worker_row=worker_row,
            row_processor=row_processor,
        )

        if row_error is None:
            result.successful_rows += 1
            continue

        result.failed_rows += 1
        result.row_errors.append(row_error)

    return result


def merge_worker_results(
    *,
    base_result: ImportWorkerResult,
    chunk_result: ImportWorkerResult,
) -> ImportWorkerResult:
    """Merge one chunk result into the main worker result."""

    base_result.processed_rows += chunk_result.processed_rows
    base_result.successful_rows += chunk_result.successful_rows
    base_result.failed_rows += chunk_result.failed_rows
    base_result.row_errors.extend(chunk_result.row_errors)

    return base_result


async def process_worker_rows(
    *,
    rows: list[ImportWorkerRow],
    row_processor: RowProcessor,
    chunk_size: int = 100,
) -> ImportWorkerResult:
    """Process normalized rows in chunks."""

    final_result = ImportWorkerResult()

    chunks = chunk_import_items(
        items=rows,
        chunk_size=chunk_size,
    )

    for chunk in chunks:
        chunk_result = await process_worker_chunk(
            chunk=chunk,
            row_processor=row_processor,
        )

        merge_worker_results(
            base_result=final_result,
            chunk_result=chunk_result,
        )

    return final_result