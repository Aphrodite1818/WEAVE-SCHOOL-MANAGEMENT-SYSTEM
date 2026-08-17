import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.curriculum_v2_schemas import (
    ClassTermDepartmentResponse,
    ClassTermDepartmentSet,
    CurriculumOfferingCreate,
    CurriculumOfferingResponse,
    CurriculumResponse,
    CurriculumSubjectCreate,
    CurriculumSubjectResponse,
    CurriculumSubjectUpdate,
)
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/tenant-admin/academics", tags=["Curriculum"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.get("/levels/{academic_level_id}/curriculum", response_model=CurriculumResponse)
async def get_curriculum(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.get_curriculum(
        db, current_admin.tenant_id, academic_level_id
    )


@router.post(
    "/levels/{academic_level_id}/curriculum/subjects",
    response_model=CurriculumSubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_curriculum_subject(
    academic_level_id: uuid.UUID,
    payload: CurriculumSubjectCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.add_subject(
        db, current_admin.tenant_id, academic_level_id, payload
    )


@router.patch(
    "/curriculum-subjects/{curriculum_subject_id}",
    response_model=CurriculumSubjectResponse,
)
async def update_curriculum_subject(
    curriculum_subject_id: uuid.UUID,
    payload: CurriculumSubjectUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.update_subject(
        db, current_admin.tenant_id, curriculum_subject_id, payload
    )


@router.get(
    "/curriculum-subjects/{curriculum_subject_id}/offerings",
    response_model=list[CurriculumOfferingResponse],
)
async def list_offerings(
    curriculum_subject_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.list_offerings(
        db, current_admin.tenant_id, curriculum_subject_id
    )


@router.post(
    "/curriculum-subjects/{curriculum_subject_id}/offerings",
    response_model=CurriculumOfferingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_offering(
    curriculum_subject_id: uuid.UUID,
    payload: CurriculumOfferingCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.add_offering(
        db, current_admin.tenant_id, curriculum_subject_id, payload
    )


@router.delete(
    "/curriculum-offerings/{offering_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_offering(
    offering_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    await AcademicCurriculumService.remove_offering(db, current_admin.tenant_id, offering_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/classes/{class_id}/terms/{academic_term_id}/department",
    response_model=ClassTermDepartmentResponse | None,
)
async def get_class_term_department(
    class_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.get_class_department(
        db, current_admin.tenant_id, class_id, academic_term_id
    )


@router.put(
    "/classes/{class_id}/terms/{academic_term_id}/department",
    response_model=ClassTermDepartmentResponse,
)
async def set_class_term_department(
    class_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    payload: ClassTermDepartmentSet,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AcademicCurriculumService.set_class_department(
        db,
        current_admin.tenant_id,
        current_admin.id,
        class_id,
        academic_term_id,
        payload.department_id,
    )


@router.delete(
    "/classes/{class_id}/terms/{academic_term_id}/department",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_class_term_department(
    class_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    await AcademicCurriculumService.clear_class_department(
        db, current_admin.tenant_id, class_id, academic_term_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
