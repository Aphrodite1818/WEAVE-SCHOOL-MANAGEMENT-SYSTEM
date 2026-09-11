from pathlib import Path

from sqlalchemy import UniqueConstraint

import app.models  # noqa: F401
from app.modules.report_cards.comment_models import (
    CommentTemplate,
    StudentTermTeacherComment,
    TeacherCommentOverride,
)
from app.modules.report_cards.models import ReportCard
from app.modules.students.models import StudentEnrollmentOutcome


def test_python_enrollment_outcomes_match_canonical_placement_contract() -> None:
    assert StudentEnrollmentOutcome.CLASS_PLACED.value == "class_placed"
    assert StudentEnrollmentOutcome.LEVEL_REASSIGNED.value == "level_reassigned"
    values = {item.value for item in StudentEnrollmentOutcome}
    assert "class_placed" in values
    assert "level_reassigned" in values


def test_initial_baseline_contains_the_canonical_enrollment_outcomes() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    migration = (
        backend_root
        / "alembic"
        / "versions"
        / "20260911_initial_schema_initial_production_schema.py"
    ).read_text(encoding="utf-8")

    assert "revision: str = '20260911_initial_schema'" in migration
    assert "down_revision: Union[str, Sequence[str], None] = None" in migration
    assert "'class_placed'" in migration
    assert "'level_reassigned'" in migration


def test_comment_templates_use_performance_ranges_not_grade_mappings() -> None:
    columns = CommentTemplate.__table__.c
    assert "minimum_score" in columns
    assert "maximum_score" in columns
    assert "is_default" in columns
    assert "name" not in columns


def test_teacher_comment_and_override_preserve_student_enrollment_context() -> None:
    comment_columns = StudentTermTeacherComment.__table__.c
    override_columns = TeacherCommentOverride.__table__.c

    for columns in (comment_columns, override_columns):
        assert "student_id" in columns
        assert "student_enrollment_id" in columns
        assert "class_id" in columns
        assert "academic_session_id" in columns
        assert "academic_term_id" in columns


def test_report_card_versioning_has_one_version_identity_and_separate_current_indexes() -> None:
    version_constraint = next(
        item
        for item in ReportCard.__table__.constraints
        if isinstance(item, UniqueConstraint)
        and item.name == "uq_report_cards_student_period_version"
    )
    assert [column.name for column in version_constraint.columns] == [
        "tenant_id",
        "student_id",
        "academic_session_id",
        "academic_term_id",
        "version",
    ]

    indexes = {index.name: index for index in ReportCard.__table__.indexes}
    published = indexes["uq_report_cards_current_published_period"]
    draft = indexes["uq_report_cards_current_draft_period"]
    assert published.unique is True
    assert draft.unique is True
    assert "published" in str(published.dialect_options["postgresql"]["where"])
    assert "superseded_at IS NULL" in str(published.dialect_options["postgresql"]["where"])
    assert "draft" in str(draft.dialect_options["postgresql"]["where"])
    assert "superseded_at IS NULL" in str(draft.dialect_options["postgresql"]["where"])


def test_report_card_has_comment_provenance_and_replacement_snapshot_fields() -> None:
    columns = ReportCard.__table__.c
    for name in (
        "academic_level_id",
        "academic_level_department_id",
        "academic_level_name_snapshot",
        "class_name_snapshot",
        "class_arm_snapshot",
        "department_name_snapshot",
        "teacher_name_snapshot",
        "teacher_comment_source",
        "teacher_comment_source_id",
        "teacher_comment_override_reason",
        "teacher_comment_override_admin_id",
        "teacher_comment_override_at",
        "principal_comment_source_template_id",
        "replaces_report_card_id",
    ):
        assert name in columns
