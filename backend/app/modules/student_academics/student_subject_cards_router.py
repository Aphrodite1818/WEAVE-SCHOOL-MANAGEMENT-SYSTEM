"""Student subject-card route exposing partial draft scores without premature grades."""

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_onboarded_student
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import StudentSubjectCardListResponse
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student

router = APIRouter(
    prefix="/students/academics",
    tags=["Student Academics"],
)

CurrentStudent: TypeAlias = Annotated[
    Student,
    Depends(get_current_onboarded_student),
]


@router.get("/subjects", response_model=StudentSubjectCardListResponse)
async def list_my_subject_cards_with_drafts(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectCardListResponse:
    """Return class-subject cards with any recorded score components.

    Draft rows may expose partial component scores and their running total. A grade
    and remark are exposed only after all three components exist and the result has
    moved beyond draft. This keeps incomplete work visible without presenting a
    provisional grade as final.
    """

    response = await StudentAcademicService.list_student_subject_cards(
        db,
        actor=current_student,
    )

    session_id = response.context.academic_session_id
    term_id = response.context.academic_term_id
    if session_id is None or term_id is None:
        return response

    for card in response.items:
        compatibility = (
            await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                db,
                current_student.tenant_id,
                card.class_id,
                card.subject_id,
            )
        )
        if compatibility is None:
            continue

        result = await StudentAcademicRepository.get_result_by_scope(
            db,
            current_student.tenant_id,
            current_student.id,
            compatibility.id,
            session_id,
            term_id,
        )
        if result is None:
            continue

        complete = all(
            value is not None
            for value in (
                result.test_score,
                result.assessment_score,
                result.exam_score,
            )
        )
        grade_visible = complete and result.status != AcademicResultStatus.DRAFT

        card.result_id = result.id
        card.test_score = result.test_score
        card.assessment_score = result.assessment_score
        card.exam_score = result.exam_score
        card.total_score = result.total_score
        card.grade = result.grade if grade_visible else None
        card.remark = result.remark if grade_visible else None
        card.status = result.status.value
        card.is_complete = complete

    return response
