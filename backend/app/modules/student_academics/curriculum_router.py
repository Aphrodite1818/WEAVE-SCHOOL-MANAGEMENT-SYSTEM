import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.schemas import (
    StudentDepartmentAssignmentCreate,
    StudentDepartmentAssignmentResponse,
    SubjectOfferingCreate,
    SubjectOfferingResponse,
)
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/tenant-admin/academics", tags=["Curriculum"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post(
    "/level-subjects/{level_subject_id}/offerings",
    response_model=SubjectOfferingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subject_offering(
    level_subject_id: uuid.UUID,
    payload: SubjectOfferingCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SubjectOfferingResponse:
    return await CurriculumResolutionService.create_subject_offering(
        db,
        tenant_id=current_admin.tenant_id,
        level_subject_id=level_subject_id,
        payload=payload,
    )


@router.get(
    "/level-subjects/{level_subject_id}/offerings",
    response_model=list[SubjectOfferingResponse],
)
async def list_subject_offerings(
    level_subject_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> list[SubjectOfferingResponse]:
    return await CurriculumResolutionService.list_subject_offerings(
        db,
        tenant_id=current_admin.tenant_id,
        level_subject_id=level_subject_id,
    )


@router.post(
    "/department-assignments",
    response_model=StudentDepartmentAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_student_department(
    payload: StudentDepartmentAssignmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDepartmentAssignmentResponse:
    return await CurriculumResolutionService.assign_student_department(
        db,
        tenant_id=current_admin.tenant_id,
        admin_id=current_admin.id,
        payload=payload,
    )
