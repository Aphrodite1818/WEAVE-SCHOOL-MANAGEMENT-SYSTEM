"""Regression contracts for the canonical Department -> level mapping cutover."""

from __future__ import annotations

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
from app.modules.cbt.sync.projectors.curriculum import project_curriculum_offering
from app.modules.cbt.sync.schemas import SYNC_SCHEMA_VERSION
from app.modules.classes.models import AcademicLevelDepartment, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    CurriculumOffering,
)
from app.modules.student_academics.curriculum_v2_schemas import (
    ClassTermDepartmentSet,
    CurriculumOfferingCreate,
)


def _unique_constraint_columns(model, name: str) -> tuple[str, ...]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if isinstance(item, UniqueConstraint) and item.name == name
    )
    return tuple(column.name for column in constraint.columns)


def test_department_is_tenant_wide_and_unique_by_normalized_name() -> None:
    assert "academic_level_id" not in Department.__table__.c
    assert _unique_constraint_columns(Department, "uq_departments_tenant_name") == (
        "tenant_id",
        "normalized_name",
    )


def test_level_department_mapping_is_the_unique_specialization_scope() -> None:
    assert _unique_constraint_columns(
        AcademicLevelDepartment,
        "uq_academic_level_departments_scope",
    ) == ("tenant_id", "academic_level_id", "department_id")


def test_operational_specialization_models_reference_level_mapping_only() -> None:
    assignment_columns = ClassTermDepartmentAssignment.__table__.c
    offering_columns = CurriculumOffering.__table__.c

    assert "academic_level_department_id" in assignment_columns
    assert "department_id" not in assignment_columns
    assert "academic_level_department_id" in offering_columns
    assert "department_id" not in offering_columns


def test_class_term_department_request_accepts_mapping_and_rejects_legacy_department_id() -> None:
    mapping_id = uuid4()
    payload = ClassTermDepartmentSet(
        academic_level_department_id=mapping_id,
    )
    assert payload.academic_level_department_id == mapping_id

    with pytest.raises(ValidationError):
        ClassTermDepartmentSet.model_validate({"department_id": str(uuid4())})


def test_curriculum_offering_request_accepts_mapping_and_rejects_legacy_department_id() -> None:
    term_id = uuid4()
    mapping_id = uuid4()
    payload = CurriculumOfferingCreate(
        academic_term_id=term_id,
        academic_level_department_id=mapping_id,
    )
    assert payload.academic_level_department_id == mapping_id

    with pytest.raises(ValidationError):
        CurriculumOfferingCreate.model_validate(
            {
                "academic_term_id": str(term_id),
                "department_id": str(uuid4()),
            }
        )


def test_cbt_v4_projects_level_department_mapping_as_department_identity() -> None:
    assert SYNC_SCHEMA_VERSION == 4

    department_source = getsource(project_department)
    assignment_source = getsource(project_class_term_department)
    offering_source = getsource(project_curriculum_offering)

    assert "AcademicLevelDepartment" in department_source
    assert "id=link.id" in department_source
    assert "academic_level_id=link.academic_level_id" in department_source
    assert "department_id=row.academic_level_department_id" in assignment_source
    assert "department_id=row.academic_level_department_id" in offering_source


def test_bulk_import_resolves_human_department_name_through_level_mapping() -> None:
    optimized_source = getsource(resolve_student_class_references_batch)
    canonical_source = getsource(BulkImportService.resolve_student_class_references)

    for source in (optimized_source, canonical_source):
        assert "AcademicLevelDepartment" in source
        assert "academic_level_department_id" in source
        assert "assignment.department_id" not in source
