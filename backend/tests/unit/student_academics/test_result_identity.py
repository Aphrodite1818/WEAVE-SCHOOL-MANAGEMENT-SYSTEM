from sqlalchemy import UniqueConstraint

from app.modules.student_academics.models import StudentSubjectResult


def test_student_subject_result_identity_is_stable_across_teacher_reassignment() -> None:
    constraint = next(
        item
        for item in StudentSubjectResult.__table__.constraints
        if isinstance(item, UniqueConstraint) and item.name == "uq_student_subject_result_scope"
    )

    assert [column.name for column in constraint.columns] == [
        "tenant_id",
        "student_id",
        "curriculum_subject_id",
        "academic_session_id",
        "academic_term_id",
    ]
