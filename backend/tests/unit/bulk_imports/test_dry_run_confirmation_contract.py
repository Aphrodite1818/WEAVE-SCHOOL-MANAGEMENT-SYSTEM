from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.bulk_imports.models import (
    ImportFileType,
    ImportJob,
    ImportJobStatus,
    ImportResourceType,
)
from app.modules.bulk_imports.service import BulkImportService


def _job(**overrides) -> ImportJob:
    values = {
        "tenant_id": uuid4(),
        "resource_type": ImportResourceType.STUDENTS,
        "file_type": ImportFileType.XLSX,
        "original_filename": "students.xlsx",
        "status": ImportJobStatus.COMPLETED,
        "total_rows": 2,
        "processed_rows": 2,
        "successful_rows": 2,
        "failed_rows": 0,
        "completed_at": datetime.now(timezone.utc),
        "metadata_json": {
            "dry_run": True,
            "confirmation_required": True,
        },
    }
    values.update(overrides)
    return ImportJob(**values)


def test_confirmation_rejects_validation_errors() -> None:
    with pytest.raises(BadRequestException, match="All rows must pass validation"):
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=_job(failed_rows=1, successful_rows=1),
            staged_row_count=1,
        )


def test_confirmation_rejects_fewer_staged_rows_than_total() -> None:
    with pytest.raises(ConflictException, match="staged valid rows"):
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=_job(total_rows=2, successful_rows=2),
            staged_row_count=1,
        )


def test_confirmation_rejects_no_valid_rows() -> None:
    with pytest.raises(BadRequestException, match="no valid rows"):
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=_job(total_rows=0, successful_rows=0),
            staged_row_count=0,
        )


def test_confirmation_rejects_repeated_confirmation() -> None:
    with pytest.raises(ConflictException, match="already been confirmed"):
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=_job(
                metadata_json={
                    "dry_run": True,
                    "confirmation_required": True,
                    "confirmed_at": "now",
                }
            ),
            staged_row_count=2,
        )


def test_confirmation_rejects_already_processing_job() -> None:
    with pytest.raises(ConflictException, match="already pending or processing"):
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=_job(status=ImportJobStatus.PROCESSING),
            staged_row_count=2,
        )


def test_confirmation_allows_fully_valid_dry_run() -> None:
    BulkImportService.validate_dry_run_confirmation_contract(
        import_job=_job(),
        staged_row_count=2,
    )
