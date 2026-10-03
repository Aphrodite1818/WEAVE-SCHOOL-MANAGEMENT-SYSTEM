"""Teacher grading-scale reads and constrained manual result entry."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_teacher
from app.modules.student_academics.schemas import (
    GradingScaleListResponse,
    StudentSubjectResultResponse,
    StudentSubjectResultUpsert,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.student_academics.teacher_result_service import TeacherResultService
from app.modules.teachers.models import TeacherMembership

router = APIRouter(
    prefix="/teachers/academics",
    tags=["Teacher Academics"],
)
CurrentTeacher: TypeAlias = Annotated[TeacherMembership, Depends(get_current_teacher)]


@router.get("/grading-scales", response_model=GradingScaleListResponse)
async def list_teacher_grading_scales(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> GradingScaleListResponse:
    items, total = await StudentAcademicService.list_grading_scales(
        db,
        current_teacher.tenant_id,
        skip=0,
        limit=100,
        active_only=True,
    )
    return GradingScaleListResponse(items=items, total=total)


@router.post("/results", response_model=StudentSubjectResultResponse)
async def save_teacher_manual_result(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentSubjectResultResponse:
    """Record only teacher-owned non-examinable assessment component scores."""

    return await TeacherResultService.upsert_manual_scores(
        db,
        teacher=current_teacher,
        payload=payload,
    )
