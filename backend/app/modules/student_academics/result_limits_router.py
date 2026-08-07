"""Result write routes with tenant-configured assessment-limit enforcement."""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_student,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.core.exceptions import BadRequestException
from app.modules.student_academics.models import (
    AcademicResultStatus,
    SchoolAssessmentConfig,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    StudentSubjectResultResponse,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

admin_router = APIRouter(prefix="/tenant-admin/academics", tags=["Tenant Admin Academics"])
teacher_router = APIRouter(prefix="/teachers/academics", tags=["Teacher Academics"])
student_router = APIRouter(prefix="/students/academics", tags=["Student Academics"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]


class AssessmentLimitsResponse(BaseModel):
    test_max: int | None = None
    assessment_max: int | None = None
    exam_max: int | None = None
    total_max: int | None = None
    is_configured: bool = False


async def _get_limits(db: DbSession, tenant_id: UUID) -> SchoolAssessmentConfig | None:
    return (
        await db.execute(
            select(SchoolAssessmentConfig).where(SchoolAssessmentConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


def _limits_response(config: SchoolAssessmentConfig | None) -> AssessmentLimitsResponse:
    if config is None:
        return AssessmentLimitsResponse(is_configured=False)
    return AssessmentLimitsResponse(
        test_max=config.test_max,
        assessment_max=config.assessment_max,
        exam_max=config.exam_max,
        total_max=config.test_max + config.assessment_max + config.exam_max,
        is_configured=True,
    )


async def _require_limits(db: DbSession, tenant_id: UUID) -> SchoolAssessmentConfig:
    config = await _get_limits(db, tenant_id)
    if config is None:
        raise BadRequestException(
            "Assessment limits have not been configured. A tenant admin must configure test, assessment, and exam maximums before scores can be recorded."
        )
    return config


def _validate_score(value, maximum: int, label: str) -> None:
    if value is None:
        return
    if value < 0:
        raise BadRequestException(f"{label} score cannot be negative.")
    if value > maximum:
        raise BadRequestException(
            f"{label} score cannot exceed the configured maximum of {maximum}."
        )


def _validate_payload(payload: StudentSubjectResultUpsert, config: SchoolAssessmentConfig) -> None:
    _validate_score(payload.test_score, config.test_max, "Test")
    _validate_score(payload.assessment_score, config.assessment_max, "Assessment")
    _validate_score(payload.exam_score, config.exam_max, "Exam")


async def _validate_existing_result(
    db: DbSession,
    tenant_id: UUID,
    result_id: UUID,
    config: SchoolAssessmentConfig,
) -> None:
    result = await StudentAcademicRepository.get_result_by_id(db, tenant_id, result_id)
    if result is None:
        return
    _validate_score(result.test_score, config.test_max, "Test")
    _validate_score(result.assessment_score, config.assessment_max, "Assessment")
    _validate_score(result.exam_score, config.exam_max, "Exam")


@admin_router.get("/assessment-limits", response_model=AssessmentLimitsResponse)
async def get_admin_assessment_limits(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AssessmentLimitsResponse:
    return _limits_response(await _get_limits(db, current_admin.tenant_id))


@teacher_router.get("/assessment-limits", response_model=AssessmentLimitsResponse)
async def get_teacher_assessment_limits(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AssessmentLimitsResponse:
    return _limits_response(await _get_limits(db, current_teacher.tenant_id))


@student_router.get("/assessment-limits", response_model=AssessmentLimitsResponse)
async def get_student_assessment_limits(
    db: DbSession,
    current_student: CurrentStudent,
) -> AssessmentLimitsResponse:
    return _limits_response(await _get_limits(db, current_student.tenant_id))


@admin_router.post("/results", response_model=StudentSubjectResultResponse)
async def upsert_admin_result_with_limits(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    config = await _require_limits(db, current_admin.tenant_id)
    _validate_payload(payload, config)
    return await StudentAcademicService.upsert_student_result(db, current_admin, payload)


@teacher_router.post("/results", response_model=StudentSubjectResultResponse)
async def upsert_teacher_result_with_limits(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentSubjectResultResponse:
    config = await _require_limits(db, current_teacher.tenant_id)
    _validate_payload(payload, config)
    return await StudentAcademicService.upsert_student_result(db, current_teacher, payload)


@admin_router.patch("/results/{result_id}/status", response_model=StudentSubjectResultResponse)
async def update_result_status_with_limits(
    result_id: UUID,
    payload: StudentSubjectResultStatusUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    if payload.status in {
        AcademicResultStatus.SUBMITTED,
        AcademicResultStatus.APPROVED,
        AcademicResultStatus.LOCKED,
    }:
        config = await _require_limits(db, current_admin.tenant_id)
        await _validate_existing_result(
            db,
            current_admin.tenant_id,
            result_id,
            config,
        )
    return await StudentAcademicService.update_result_status(
        db,
        current_admin,
        result_id,
        payload,
    )
