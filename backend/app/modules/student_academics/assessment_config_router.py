"""Tenant assessment-scheme management and actor read routes."""

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_student,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.modules.student_academics.assessment_repository import AssessmentRepository
from app.modules.student_academics.assessment_schemas import (
    AssessmentComponentCreate,
    AssessmentComponentOrder,
    AssessmentComponentUpdate,
    AssessmentSchemeCreate,
    AssessmentSchemeListResponse,
    AssessmentSchemeResponse,
    AssessmentSchemeUpdate,
)
from app.modules.student_academics.assessment_service import AssessmentService
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/assessment-schemes", tags=["Tenant Admin Academics"]
)
teacher_router = APIRouter(prefix="/teachers/academics", tags=["Teacher Academics"])
student_router = APIRouter(prefix="/students/academics", tags=["Student Academics"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]


@router.get("", response_model=AssessmentSchemeListResponse)
async def list_schemes(db: DbSession, current_admin: CurrentTenantAdmin):
    rows = await AssessmentRepository.list_schemes(db, current_admin.tenant_id)
    components_by_scheme = await AssessmentRepository.list_components_for_schemes(
        db,
        current_admin.tenant_id,
        {row.id for row in rows},
    )
    items = [
        await AssessmentService.response(
            db,
            row,
            components=components_by_scheme.get(row.id, []),
        )
        for row in rows
    ]
    return AssessmentSchemeListResponse(items=items, total=len(items))


@router.get("/active", response_model=AssessmentSchemeResponse)
async def get_active_scheme(db: DbSession, current_admin: CurrentTenantAdmin):
    return await AssessmentService.active(db, current_admin.tenant_id)


@router.post("", response_model=AssessmentSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    payload: AssessmentSchemeCreate, db: DbSession, current_admin: CurrentTenantAdmin
):
    return await AssessmentService.create(db, current_admin.tenant_id, payload)


@router.patch("/{scheme_id}", response_model=AssessmentSchemeResponse)
async def update_scheme(
    scheme_id: uuid.UUID,
    payload: AssessmentSchemeUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AssessmentService.rename(db, current_admin.tenant_id, scheme_id, payload)


@router.post("/{scheme_id}/components", response_model=AssessmentSchemeResponse)
async def add_component(
    scheme_id: uuid.UUID,
    payload: AssessmentComponentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AssessmentService.add_component(db, current_admin.tenant_id, scheme_id, payload)


@router.patch("/{scheme_id}/components/{component_id}", response_model=AssessmentSchemeResponse)
async def update_component(
    scheme_id: uuid.UUID,
    component_id: uuid.UUID,
    payload: AssessmentComponentUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AssessmentService.update_component(
        db, current_admin.tenant_id, scheme_id, component_id, payload
    )


@router.delete(
    "/{scheme_id}/components/{component_id}",
    response_model=AssessmentSchemeResponse,
)
async def remove_component(
    scheme_id: uuid.UUID,
    component_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AssessmentService.remove_component(
        db, current_admin.tenant_id, scheme_id, component_id
    )


@router.put("/{scheme_id}/component-order", response_model=AssessmentSchemeResponse)
async def reorder_components(
    scheme_id: uuid.UUID,
    payload: AssessmentComponentOrder,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await AssessmentService.reorder(db, current_admin.tenant_id, scheme_id, payload)


@router.post("/{scheme_id}/activate", response_model=AssessmentSchemeResponse)
async def activate_scheme(scheme_id: uuid.UUID, db: DbSession, current_admin: CurrentTenantAdmin):
    return await AssessmentService.activate(db, current_admin.tenant_id, scheme_id)


@teacher_router.get("/assessment-scheme", response_model=AssessmentSchemeResponse)
async def get_teacher_assessment_scheme(db: DbSession, current_teacher: CurrentTeacher):
    return await AssessmentService.active(db, current_teacher.tenant_id)


@student_router.get("/assessment-scheme", response_model=AssessmentSchemeResponse)
async def get_student_assessment_scheme(db: DbSession, current_student: CurrentStudent):
    return await AssessmentService.active(db, current_student.tenant_id)