from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.normalizers import BulkImportNormalizer
from app.modules.bulk_imports.service import BulkImportService
from app.modules.bulk_imports.templates import DATA_HEADERS_BY_RESOURCE, TEMPLATE_VERSION_BY_RESOURCE
from app.modules.bulk_imports.validators import BulkImportValidator, ImportRowValidationResult
from app.modules.classes.repository import (
    AcademicLevelRepository,
    ArmLabelRepository,
    ClassRoomRepository,
    DepartmentRepository,
)
from app.modules.student_academics.repository import StudentAcademicRepository


def _active_level(level_id, name="JSS1"):
    return SimpleNamespace(
        id=level_id,
        name=name,
        is_active=True,
        archived_at=None,
    )


def _active_arm(arm_id, label="A"):
    return SimpleNamespace(
        id=arm_id,
        label=label,
        is_active=True,
        archived_at=None,
    )


def _active_class(class_id):
    return SimpleNamespace(
        id=class_id,
        is_active=True,
        archived_at=None,
    )


def _active_department(department_id, name="Science"):
    return SimpleNamespace(
        id=department_id,
        name=name,
        normalized_name=name.casefold(),
        is_active=True,
        archived_at=None,
    )


def test_student_template_contract_uses_level_arm_and_department() -> None:
    assert TEMPLATE_VERSION_BY_RESOURCE[ImportResourceType.STUDENTS] == "students_v7"
    assert DATA_HEADERS_BY_RESOURCE[ImportResourceType.STUDENTS][4:7] == [
        "level",
        "arm",
        "department",
    ]
    assert "class" not in DATA_HEADERS_BY_RESOURCE[ImportResourceType.STUDENTS]


def test_student_import_requires_level_and_arm() -> None:
    normalized, ignored = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Level": " jss 1 ",
            "Arm": " a ",
            "Department": " Science ",
        },
    )
    assert ignored == []
    assert normalized["level"] == "JSS1"
    assert normalized["arm"] == "A"
    assert normalized["department"] == "Science"

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
    assert {error.field_name for error in result.errors} == {"level", "arm"}


def test_student_import_does_not_accept_legacy_class_column() -> None:
    normalized, ignored = BulkImportNormalizer.normalize_row(
        resource_type=ImportResourceType.STUDENTS,
        raw_row={
            "First Name": "Ada",
            "Last Name": "Lovelace",
            "Date of Birth": "2018-01-01",
            "Level": "JSS1",
            "Class": "JSS1 A",
        },
    )
    assert "Class" in ignored
    assert "arm" not in normalized


@pytest.mark.asyncio
async def test_student_import_resolves_level_and_arm_for_general_class(monkeypatch) -> None:
    tenant_id, level_id, arm_id, class_id, term_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id)),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=_active_arm(arm_id)),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_arm_label",
        AsyncMock(return_value=_active_class(class_id)),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=SimpleNamespace(id=term_id)),
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(return_value=None),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2018-01-01",
            "level": "JSS1",
            "arm": "A",
            "department": None,
        },
    )
    db = SimpleNamespace()

    await BulkImportService.resolve_student_class_references(
        db=db,
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors == []
    assert row.normalized_row["academic_level_id"] == str(level_id)
    assert row.normalized_row["class_id"] == str(class_id)
    assert row.normalized_row["arm"] == "A"
    assert row.normalized_row["department"] is None
    ClassRoomRepository.get_by_level_arm_label.assert_awaited_once_with(
        db=db,
        tenant_id=tenant_id,
        academic_level_id=level_id,
        arm_label_id=arm_id,
    )


@pytest.mark.asyncio
async def test_student_import_requires_matching_current_term_department(monkeypatch) -> None:
    tenant_id, level_id, arm_id, class_id, term_id, department_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    department = _active_department(department_id)
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id, "SS2")),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=_active_arm(arm_id)),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_arm_label",
        AsyncMock(return_value=_active_class(class_id)),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=SimpleNamespace(id=term_id)),
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(return_value=SimpleNamespace(department_id=department_id)),
    )
    monkeypatch.setattr(
        DepartmentRepository,
        "get_by_id",
        AsyncMock(return_value=department),
    )
    monkeypatch.setattr(
        DepartmentRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=department),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "level": "SS2",
            "arm": "A",
            "department": "science",
        },
    )
    db = SimpleNamespace()

    await BulkImportService.resolve_student_class_references(
        db=db,
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors == []
    assert row.normalized_row["class_id"] == str(class_id)
    assert row.normalized_row["department"] == "Science"
    DepartmentRepository.get_by_normalized_name.assert_awaited_once_with(
        db,
        tenant_id,
        level_id,
        "science",
    )


@pytest.mark.asyncio
async def test_student_import_requires_department_for_specialized_class(monkeypatch) -> None:
    tenant_id, level_id, arm_id, class_id, term_id, department_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id, "SS2")),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=_active_arm(arm_id)),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_arm_label",
        AsyncMock(return_value=_active_class(class_id)),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=SimpleNamespace(id=term_id)),
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(return_value=SimpleNamespace(department_id=department_id)),
    )
    monkeypatch.setattr(
        DepartmentRepository,
        "get_by_id",
        AsyncMock(return_value=_active_department(department_id)),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={"level": "SS2", "arm": "A", "department": None},
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "department"
    assert row.errors[0].error_code == "department_required"


@pytest.mark.asyncio
async def test_student_import_rejects_department_for_general_class(monkeypatch) -> None:
    tenant_id, level_id, arm_id, class_id, term_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id, "SS2")),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=_active_arm(arm_id)),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_arm_label",
        AsyncMock(return_value=_active_class(class_id)),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=SimpleNamespace(id=term_id)),
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(return_value=None),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={"level": "SS2", "arm": "A", "department": "Science"},
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "department"
    assert row.errors[0].error_code == "department_not_applicable"


@pytest.mark.asyncio
async def test_student_import_rejects_wrong_department_for_specialized_class(monkeypatch) -> None:
    tenant_id, level_id, arm_id, class_id, term_id, science_id, art_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    science = _active_department(science_id, "Science")
    art = _active_department(art_id, "Art")
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id, "SS2")),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=_active_arm(arm_id)),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_level_arm_label",
        AsyncMock(return_value=_active_class(class_id)),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=SimpleNamespace(id=term_id)),
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(return_value=SimpleNamespace(department_id=science_id)),
    )
    monkeypatch.setattr(
        DepartmentRepository,
        "get_by_id",
        AsyncMock(return_value=science),
    )
    monkeypatch.setattr(
        DepartmentRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=art),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={"level": "SS2", "arm": "A", "department": "Art"},
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "department"
    assert row.errors[0].error_code == "department_mismatch"


@pytest.mark.asyncio
async def test_student_import_cannot_invent_new_arm_label(monkeypatch) -> None:
    tenant_id, level_id = uuid4(), uuid4()
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_normalized_name",
        AsyncMock(return_value=_active_level(level_id, "SS2")),
    )
    monkeypatch.setattr(
        ArmLabelRepository,
        "get_by_normalized_label",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=None),
    )
    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "level": "SS2",
            "arm": "Z",
        },
    )

    await BulkImportService.resolve_student_class_references(
        db=SimpleNamespace(),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "arm"
    assert row.errors[0].error_code == "arm_label_not_found"
