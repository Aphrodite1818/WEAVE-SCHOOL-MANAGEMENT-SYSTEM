"""Regression checks for the pre-launch academic/CBT cutover contract."""

from sqlalchemy import UniqueConstraint

from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.cbt.sync.projectors.registry import PROJECTORS
from app.modules.classes.models import AcademicLevel, AcademicLevelDepartment, Department
from app.modules.student_academics.curriculum_models import CurriculumSubjectDepartment
from app.modules.student_academics.models import StudentProgressionRun


def _constraint(table, name: str) -> UniqueConstraint:
    constraint = next(
        item
        for item in table.constraints
        if isinstance(item, UniqueConstraint) and item.name == name
    )
    return constraint


def test_department_pool_and_level_mapping_uniqueness_are_explicit() -> None:
    constraint = _constraint(Department.__table__, "uq_departments_tenant_name")
    assert [column.name for column in constraint.columns] == [
        "tenant_id",
        "normalized_name",
    ]
    mapping_constraint = _constraint(
        AcademicLevelDepartment.__table__, "uq_academic_level_departments_scope"
    )
    assert [column.name for column in mapping_constraint.columns] == [
        "tenant_id",
        "academic_level_id",
        "department_id",
    ]


def test_academic_level_specialization_threshold_contract_is_explicit() -> None:
    column = AcademicLevel.__table__.c.specialization_required_from_term_position
    assert column.nullable is True


def test_progression_run_persists_terminal_graduation_approval() -> None:
    column = StudentProgressionRun.__table__.c.terminal_completion_approved
    assert column.nullable is False
    assert str(column.server_default.arg).lower() == "false"


def test_curriculum_subject_department_scope_is_persistent_and_unique() -> None:
    constraint = _constraint(
        CurriculumSubjectDepartment.__table__,
        "uq_curriculum_subject_department_scope",
    )
    assert [column.name for column in constraint.columns] == [
        "tenant_id",
        "curriculum_subject_id",
        "academic_level_department_id",
    ]
    assert "academic_term_id" not in CurriculumSubjectDepartment.__table__.c


def test_cbt_sync_contract_includes_tenant_admins() -> None:
    assert CBTSyncEntityType.ADMIN.value == "admin"
    assert CBTSyncEntityType.ADMIN in PROJECTORS
