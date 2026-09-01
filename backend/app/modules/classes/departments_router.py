import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin, get_current_tenant_member
from app.modules.classes.schemas import (
    DepartmentActivateRequest,
    DepartmentArchiveRequest,
    DepartmentCreate,
    DepartmentDeactivateRequest,
    DepartmentDeleteRequest,
    DepartmentResponse,
    DepartmentRestoreRequest,
    DepartmentUpdate,
)
from app.modules.classes.service import DepartmentService
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/academic-levels/{academic_level_id}/departments", tags=["Departments"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent, Depends(get_current_tenant_member)
]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    academic_level_id: uuid.UUID,
    payload: DepartmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await DepartmentService.create(db, current_admin, academic_level_id, payload)


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_member: CurrentTenantMember,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
):
    return await DepartmentService.list(
        db,
        current_member,
        academic_level_id,
        active_only=active_only,
        include_archived=include_archived,
    )


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await DepartmentService.update(
        db,
        current_admin,
        department_id,
        payload,
        academic_level_id=academic_level_id,
    )


@router.post("/{department_id}/activate", response_model=DepartmentResponse)
async def activate_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentActivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentService.activate(
        db, current_admin, department_id, academic_level_id=academic_level_id
    )


@router.post("/{department_id}/deactivate", response_model=DepartmentResponse)
async def deactivate_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentDeactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentService.deactivate(
        db, current_admin, department_id, academic_level_id=academic_level_id
    )


@router.post("/{department_id}/archive", response_model=DepartmentResponse)
async def archive_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentService.archive(
        db, current_admin, department_id, academic_level_id=academic_level_id
    )


@router.post("/{department_id}/restore", response_model=DepartmentResponse)
async def restore_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentRestoreRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentService.restore(
        db, current_admin, department_id, academic_level_id=academic_level_id
    )


@router.delete("/{department_id}", response_model=DepartmentResponse)
async def delete_department(
    academic_level_id: uuid.UUID,
    department_id: uuid.UUID,
    payload: DepartmentDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentService.hard_delete(
        db, current_admin, department_id, academic_level_id=academic_level_id
    )
