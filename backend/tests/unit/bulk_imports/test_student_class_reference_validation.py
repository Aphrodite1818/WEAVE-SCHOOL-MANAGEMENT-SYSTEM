from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.normalizers import BulkImportNormalizer
from app.modules.bulk_imports.service import BulkImportService
from app.modules.bulk_imports.validators import BulkImportValidator, ImportRowValidationResult
from app.modules.classes.repository import ClassRoomRepository


def test_student_import_normalizes_class_fields_like_class_creation() -> None:
    normalized_row, ignored_fields = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Class": " junior secondary school 1 ",
            "Arm": " a ",
        },
    )

    assert ignored_fields == []
    assert normalized_row["class_name"] == "JUNIOR SECONDARY SCHOOL 1"
    assert normalized_row["class_arm"] == "A"


def test_student_import_normalizes_no_arm_without_import_sentinel() -> None:
    normalized_row, ignored_fields = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Class": "JSS 1",
            "Arm": "no arm",
        },
    )

    assert ignored_fields == []
    assert normalized_row["class_name"] == "JSS1"
    assert normalized_row["class_arm"] is None


def test_student_import_dry_run_rejects_future_date_of_birth() -> None:
    future_date = date.today() + timedelta(days=1)
    validation_result = BulkImportValidator.validate_row(
        resource_type=ImportResourceType.STUDENTS,
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": future_date.isoformat(),
        },
        ignored_fields=[],
    )

    assert not validation_result.is_valid
    assert any(
        error.field_name == "date_of_birth"
        and error.error_code == "date_not_before_today"
        and error.error_message == "date_of_birth must be before today."
        for error in validation_result.errors
    )


@pytest.mark.asyncio
async def test_student_import_resolves_uppercase_class_reference(monkeypatch) -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    calls: list[dict[str, object]] = []

    async def get_by_normalized_name_and_arm(db, tenant_id, class_name, class_arm=None):
        calls.append({"class_name": class_name, "class_arm": class_arm})
        return SimpleNamespace(
            id=class_id,
            name="JSS1",
            arm="A",
            is_active=True,
            archived_at=None,
        )

    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_normalized_name_and_arm",
        get_by_normalized_name_and_arm,
    )
    validation_result = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
            "class_name": "JSS1",
            "class_arm": "A",
        },
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[validation_result],
    )

    assert validation_result.errors == []
    assert calls == [{"class_name": "JSS1", "class_arm": "A"}]
    assert validation_result.normalized_row["class_id"] == str(class_id)
    assert validation_result.normalized_row["class_name"] == "JSS1"
    assert validation_result.normalized_row["class_arm"] == "A"
    assert validation_result.normalized_row["arm"] == "A"


@pytest.mark.asyncio
async def test_student_import_allows_class_name_only_for_no_arm_class(monkeypatch) -> None:
    tenant_id = uuid4()
    class_id = uuid4()
    calls: list[dict[str, object]] = []

    async def get_by_normalized_name_and_arm(db, tenant_id, class_name, class_arm=None):
        calls.append({"class_name": class_name, "class_arm": class_arm})
        return SimpleNamespace(
            id=class_id,
            name="JSS1",
            arm=None,
            is_active=True,
            archived_at=None,
        )

    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_normalized_name_and_arm",
        get_by_normalized_name_and_arm,
    )
    validation_result = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
            "class_name": "JSS1",
            "class_arm": None,
        },
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[validation_result],
    )

    assert validation_result.errors == []
    assert calls == [{"class_name": "JSS1", "class_arm": None}]
    assert validation_result.normalized_row["class_id"] == str(class_id)
    assert validation_result.normalized_row["class_arm"] is None
    assert validation_result.normalized_row["arm"] is None


@pytest.mark.asyncio
async def test_student_import_rejects_class_arm_without_class_name() -> None:
    validation_result = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
            "class_arm": "A",
        },
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=uuid4(),
        validation_results=[validation_result],
    )

    assert len(validation_result.errors) == 1
    assert validation_result.errors[0].field_name == "class_name"
    assert validation_result.errors[0].error_code == "required_with_class_arm"
