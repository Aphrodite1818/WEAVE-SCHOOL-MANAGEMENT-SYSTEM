from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.normalizers import BulkImportNormalizer
from app.modules.bulk_imports.service import BulkImportService
from app.modules.bulk_imports.templates import (
    DATA_HEADERS_BY_RESOURCE,
    TEMPLATE_VERSION_BY_RESOURCE,
)
from app.modules.bulk_imports.validators import BulkImportValidator, ImportRowValidationResult
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.classes.models import AcademicLevelStatus
from app.modules.classes.repository import (
    AcademicLevelRepository,
    ArmLabelRepository,
    ClassRoomRepository,
)
from app.modules.student_academics.repository import StudentAcademicRepository


def _mock_department_context(monkeypatch, level_id, assigned):
    assigned_link = SimpleNamespace(
        id=uuid4(),
        academic_level_id=level_id,
        department=assigned,
        is_active=True,
        archived_at=None,
    )
    monkeypatch.setattr(
        BulkImportService,
        "_get_class_term_department_assignment",
        AsyncMock(
            return_value=SimpleNamespace(
                academic_level_department_id=assigned_link.id,
            )
        ),
    )
    monkeypatch.setattr(
        AcademicLevelDepartmentRepository,
        "get_by_id",
        AsyncMock(return_value=assigned_link),
    )
    return assigned_link


def _active_level(level_id, name="JSS1"):
    return SimpleNamespace(
        id=level_id,
        name=name,
        normalized_name=name,
        status=AcademicLevelStatus.ACTIVE,
        archived_at=None,
    )


def _active_arm(arm_id, label="A"):
    return SimpleNamespace(
        id=arm_id,
        label=label,
        normalized_label=label,
        is_active=True,
        archived_at=None,
    )


def _active_class(class_id, level_id=None, arm_id=None):
    return SimpleNamespace(
        id=class_id,
        academic_level_id=level_id,
        arm_label_id=arm_id,
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


class _Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self.rows)


def _batch_db(levels, arms, classes, assignments=(), mappings=()):
    return SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _Result(levels),
                _Result(arms),
                _Result(classes),
                *([_Result(assignments)] if classes else []),
                _Result(mappings),
            ]
        )
    )


def test_student_template_contract_uses_level_and_arm_without_department() -> None:
    assert TEMPLATE_VERSION_BY_RESOURCE[ImportResourceType.STUDENTS] == "students_v8"
    headers = DATA_HEADERS_BY_RESOURCE[ImportResourceType.STUDENTS]
    assert headers[4:6] == ["level", "arm"]
    assert "department" not in headers
    assert "class" not in headers


def test_student_import_requires_level_and_arm_and_does_not_accept_department_input() -> None:
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
    assert ignored == ["Department"]
    assert normalized["level"] == "JSS1"
    assert normalized["arm"] == "A"
    assert "department" not in normalized

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
            "department": "Stale value from an earlier dry run",
        },
    )
    db = _batch_db(
        [_active_level(level_id)],
        [_active_arm(arm_id)],
        [_active_class(class_id, level_id, arm_id)],
        [],
        [],
    )

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


@pytest.mark.asyncio
async def test_student_import_derives_current_term_department_from_class(monkeypatch) -> None:
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

    _mock_department_context(monkeypatch, level_id, department)

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "level": "SS2",
            "arm": "A",
        },
    )

    await BulkImportService.resolve_student_class_references(
        db=_batch_db(
            [_active_level(level_id, "SS2")],
            [_active_arm(arm_id)],
            [_active_class(class_id, level_id, arm_id)],
        ),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors == []
    assert row.normalized_row["class_id"] == str(class_id)
    assert row.normalized_row["department"] == "Science"


@pytest.mark.asyncio
async def test_student_import_rejects_invalid_class_department_assignment(monkeypatch) -> None:
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
        AsyncMock(return_value=SimpleNamespace(academic_level_department_id=uuid4())),
    )
    monkeypatch.setattr(
        AcademicLevelDepartmentRepository,
        "get_by_id",
        AsyncMock(return_value=None),
    )

    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={"level": "SS2", "arm": "A"},
    )

    await BulkImportService.resolve_student_class_references(
        db=_batch_db(
            [_active_level(level_id, "SS2")],
            [_active_arm(arm_id)],
            [_active_class(class_id, level_id, arm_id)],
        ),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "arm"
    assert row.errors[0].error_code == "class_department_assignment_invalid"


@pytest.mark.asyncio
async def test_worker_creation_reresolves_class_department_before_student_creation(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    row = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "level": "SS2",
            "arm": "A",
            "department": "Arts",
        },
    )

    async def refresh_references(*, db, tenant_id, validation_results):
        assert tenant_id == actor.tenant_id
        validation_results[0].normalized_row["department"] = "Science"

    resolver = AsyncMock(side_effect=refresh_references)
    creator = AsyncMock(
        return_value=SimpleNamespace(
            student=SimpleNamespace(
                first_name="Ada",
                last_name="Lovelace",
                admission_number="ADM001",
            ),
            setup_code="12345678",
            access_code_expires_at=SimpleNamespace(isoformat=lambda: "2026-09-08T12:00:00+00:00"),
            parent_invitation_count=0,
        )
    )
    monkeypatch.setattr(BulkImportService, "resolve_student_class_references", resolver)
    monkeypatch.setattr(BulkImportService, "create_student_from_row", creator)

    result = await BulkImportService.process_valid_row(
        db=SimpleNamespace(),
        actor=actor,
        resource_type=ImportResourceType.STUDENTS,
        validation_result=row,
        school_name="Test School",
    )

    assert result["department"] == "Science"
    resolver.assert_awaited_once()
    creator.assert_awaited_once()


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
        db=_batch_db([_active_level(level_id, "SS2")], [], [], [], []),
        tenant_id=tenant_id,
        validation_results=[row],
    )

    assert row.errors[0].field_name == "arm"
    assert row.errors[0].error_code == "arm_label_not_found"
