"""Regression contracts for persistent curriculum department applicability."""

from inspect import getsource
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.modules.bulk_imports.optimized_validation import resolve_student_class_references_batch
from app.modules.bulk_imports.service import BulkImportService
from app.modules.cbt.sync.projectors.academics import (
    project_class_term_department,
    project_department,
)
from app.modules.cbt.sync.projectors.curriculum import project_curriculum_subject_department
from app.modules.cbt.sync.schemas import SYNC_SCHEMA_VERSION
from app.modules.classes.models import AcademicLevelDepartment, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.curriculum_v2_schemas import (
    ClassTermDepartmentSet,
    CurriculumSubjectCreate,
)


def _unique_columns(model, name: str) -> tuple[str, ...]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if isinstance(item, UniqueConstraint) and item.name == name
    )
    return tuple(column.name for column in constraint.columns)


def test_canonical_department_and_level_mapping_uniqueness() -> None:
    assert "academic_level_id" not in Department.__table__.c
    assert _unique_columns(Department, "uq_departments_tenant_name") == (
        "tenant_id",
        "normalized_name",
    )
    assert _unique_columns(
        AcademicLevelDepartment,
        "uq_academic_level_departments_scope",
    ) == ("tenant_id", "academic_level_id", "department_id")


def test_operational_scopes_reference_level_department_identity() -> None:
    assert "academic_level_department_id" in ClassTermDepartmentAssignment.__table__.c
    assert "academic_level_department_id" in CurriculumSubjectDepartment.__table__.c
    assert "academic_term_id" not in CurriculumSubjectDepartment.__table__.c


def test_requests_reject_legacy_department_id() -> None:
    mapping_id = uuid4()
    assert (
        ClassTermDepartmentSet(academic_level_department_id=mapping_id).academic_level_department_id
        == mapping_id
    )
    with pytest.raises(ValidationError):
        ClassTermDepartmentSet.model_validate({"department_id": str(uuid4())})
    with pytest.raises(ValidationError):
        CurriculumSubjectCreate.model_validate(
            {"subject_id": str(uuid4()), "department_id": str(uuid4())}
        )


def test_cbt_current_schema_projects_persistent_department_scopes() -> None:
    assert SYNC_SCHEMA_VERSION == 5
    department_source = getsource(project_department)
    assignment_source = getsource(project_class_term_department)
    scope_source = getsource(project_curriculum_subject_department)
    assert "AcademicLevelDepartment" in department_source
    assert "id=link.id" in department_source
    assert "department_id=row.academic_level_department_id" in assignment_source
    assert "department_id=scope.academic_level_department_id" in scope_source


def test_bulk_import_resolves_department_through_level_mapping() -> None:
    for source in (
        getsource(resolve_student_class_references_batch),
        getsource(BulkImportService.resolve_student_class_references),
    ):
        assert "AcademicLevelDepartment" in source
        assert "academic_level_department_id" in source
        assert "assignment.department_id" not in source
