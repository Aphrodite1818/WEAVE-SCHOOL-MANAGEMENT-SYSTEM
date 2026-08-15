from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.normalizers import BulkImportNormalizer
from app.modules.bulk_imports.service import BulkImportService
from app.modules.bulk_imports.validators import BulkImportValidator, ImportRowValidationResult
from app.modules.classes.repository import AcademicLevelRepository, ClassRoomRepository


def test_student_import_requires_level_and_allows_optional_class() -> None:
    normalized, ignored = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Level": " jss 1 ",
            "Class": " a ",
        },
    )
    assert ignored == []
    assert normalized["level"] == "JSS1"
    assert normalized["class"] == "A"

    result = BulkImportValidator.validate_row(
        resource_type=ImportResourceType.STUDENTS,
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
        },
        ignored_fields=[],
    )
    assert {error.field_name for error in result.errors} == {"level"}


def test_student_import_does_not_parse_level_from_class() -> None:
    normalized, ignored = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Class": "JSS1 A",
        },
    )
    assert ignored == []
    assert "level" not in normalized
    assert normalized["class"] == "JSS1A"


@pytest.mark.asyncio
async def test_student_import_resolves_level_then_arm(monkeypatch) -> None:
    tenant_id, level_id, class_id = uuid4(), uuid4(), uuid4()
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(
            return_value=SimpleNamespace(id=level_id, name="JSS1", is_active=True, archived_at=None)
        ),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_and_arm",
        AsyncMock(
            return_value=SimpleNamespace(id=class_id, arm="A", is_active=True, archived_at=None)
        ),
    )
    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
            "level": "JSS1",
            "class": "A",
        },
    )
    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(), tenant_id=tenant_id, validation_results=[row]
    )
    assert row.errors == []
    assert row.normalized_row["academic_level_id"] == str(level_id)
    assert row.normalized_row["class_id"] == str(class_id)


@pytest.mark.asyncio
async def test_student_import_keeps_class_unassigned_when_blank(monkeypatch) -> None:
    tenant_id, level_id = uuid4(), uuid4()
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=SimpleNamespace(id=level_id, name="JSS1")),
    )
    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={"level": "JSS1", "class": None},
    )
    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(), tenant_id=tenant_id, validation_results=[row]
    )
    assert row.normalized_row["academic_level_id"] == str(level_id)
    assert row.normalized_row["class_id"] is None
