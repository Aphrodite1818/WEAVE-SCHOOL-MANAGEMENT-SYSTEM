from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_parent, get_current_student
from app.modules.parents.models import Parent
from app.modules.student_academics.schemas import StudentSubjectCardListResponse
from app.modules.student_academics.subject_card_service import StudentSubjectCardService
from app.modules.students.models import Student


student_router = APIRouter(
    prefix="/students/academics",
    tags=["Student Academics"],
)
parent_router = APIRouter(
    prefix="/parents/academics",
    tags=["Parent Academics"],
)

CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]


@student_router.get("/subjects", response_model=StudentSubjectCardListResponse)
async def list_my_current_subject_cards(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectCardListResponse:
    return await StudentSubjectCardService.list_current_subject_cards(
        db,
        actor=current_student,
    )


@parent_router.get(
    "/students/{student_id}/subjects",
    response_model=StudentSubjectCardListResponse,
)
async def list_child_current_subject_cards(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
) -> StudentSubjectCardListResponse:
    return await StudentSubjectCardService.list_current_subject_cards(
        db,
        actor=current_parent,
        student_id=student_id,
    )
