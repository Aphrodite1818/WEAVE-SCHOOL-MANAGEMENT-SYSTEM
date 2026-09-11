"""Canonical curriculum scope checks after the pre-production baseline reset."""

from sqlalchemy import ForeignKeyConstraint

import app.models  # noqa: F401
from app.shared.base_model import Base


def test_initial_schema_excludes_obsolete_term_specific_curriculum_tables() -> None:
    table_names = {table.name for table in Base.metadata.tables.values()}
    assert "curriculum_offerings" not in table_names
    assert "subject_offerings" not in table_names
    assert "level_subjects" not in table_names


def test_persistent_scope_foreign_keys_include_tenant_identity() -> None:
    table = next(
        table
        for table in Base.metadata.tables.values()
        if table.name == "curriculum_subject_departments"
    )
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert constraints["fk_curriculum_subject_department_tenant_subject"] == (
        "tenant_id",
        "curriculum_subject_id",
    )
    assert constraints["fk_curriculum_subject_department_tenant_level_department"] == (
        "tenant_id",
        "academic_level_department_id",
    )
