"""Regression checks for the pre-launch academic/CBT cutover contract."""

from sqlalchemy import UniqueConstraint

from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.cbt.sync.projectors.registry import PROJECTORS
from app.modules.classes.models import AcademicLevel, Department
from app.modules.student_academics.curriculum_models import CurriculumOffering
from app.modules.student_academics.models import StudentProgressionRun


def _constraint(table, name: str) -> UniqueConstraint:
    constraint = next(
        item
        for item in table.constraints
        if isinstance(item, UniqueConstraint) and item.name == name
    )
    return constraint


def test_department_name_uniqueness_is_level_scoped() -> None:
    constraint = _constraint(Department.__table__, "uq_departments_tenant_level_name")
    assert [column.name for column in constraint.columns] == [
        "tenant_id",
        "academic_level_id",
        "normalized_name",
    ]
    assert not any(
        isinstance(item, UniqueConstraint)
        and [column.name for column in item.columns] == ["tenant_id", "normalized_name"]
        for item in Department.__table__.constraints
    )


def test_obsolete_specialization_threshold_contract_is_gone() -> None:
    assert "specialization_required_from_term_position" not in AcademicLevel.__dict__
    assert "specialization_required_from_term_position" not in AcademicLevel.__table__.c


def test_progression_run_persists_terminal_graduation_approval() -> None:
    column = StudentProgressionRun.__table__.c.terminal_completion_approved
    assert column.nullable is False
    assert str(column.server_default.arg).lower() == "false"


def test_general_curriculum_offering_uniqueness_uses_nulls_not_distinct() -> None:
    constraint = _constraint(CurriculumOffering.__table__, "uq_curriculum_offering_scope")
    assert [column.name for column in constraint.columns] == [
        "tenant_id",
        "curriculum_subject_id",
        "academic_term_id",
        "department_id",
    ]
    assert constraint.dialect_options["postgresql"]["nulls_not_distinct"] is True


def test_cbt_sync_contract_includes_tenant_admins() -> None:
    assert CBTSyncEntityType.ADMIN.value == "admin"
    assert CBTSyncEntityType.ADMIN in PROJECTORS
