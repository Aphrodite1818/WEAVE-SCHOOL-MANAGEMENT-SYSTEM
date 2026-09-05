import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.classes.department_service import DepartmentPoolService
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.classes.schemas import (
    AcademicLevelDepartmentActivateRequest,
    AcademicLevelDepartmentArchiveRequest,
    AcademicLevelDepartmentCreate,
    AcademicLevelDepartmentDeactivateRequest,
    AcademicLevelDepartmentDeleteRequest,
    AcademicLevelDepartmentResponse,
    AcademicLevelDepartmentRestoreRequest,
    DepartmentActivateRequest,
    DepartmentArchiveRequest,
    DepartmentCreate,
    DepartmentDeactivateRequest,
    DepartmentDeleteRequest,
    DepartmentResponse,
    DepartmentRestoreRequest,
    DepartmentUpdate,
)
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/tenant-admin/academics", tags=["Departments"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, db: DbSession, current_admin: CurrentTenantAdmin
):
    return await DepartmentPoolService.create_department(db, current_admin, payload)


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
):
    return await DepartmentPoolService.list_departments(
        db, current_admin, active_only=active_only, include_archived=include_archived
    )


@router.get("/level-department-availability", response_model=list[AcademicLevelDepartmentResponse])
async def list_level_department_availability(db: DbSession, current_admin: CurrentTenantAdmin):
    rows = await AcademicLevelDepartmentRepository.list_for_level(
        db, current_admin.tenant_id, None, include_archived=True
    )
    return [DepartmentPoolService._link_response(row) for row in rows]


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await DepartmentPoolService.update_department(db, current_admin, department_id, payload)


@router.post("/departments/{department_id}/activate", response_model=DepartmentResponse)
async def activate_department(
    department_id: uuid.UUID,
    payload: DepartmentActivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.activate_department(db, current_admin, department_id)


@router.post("/departments/{department_id}/deactivate", response_model=DepartmentResponse)
async def deactivate_department(
    department_id: uuid.UUID,
    payload: DepartmentDeactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.deactivate_department(db, current_admin, department_id)


@router.post("/departments/{department_id}/archive", response_model=DepartmentResponse)
async def archive_department(
    department_id: uuid.UUID,
    payload: DepartmentArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.archive_department(db, current_admin, department_id)


@router.post("/departments/{department_id}/restore", response_model=DepartmentResponse)
async def restore_department(
    department_id: uuid.UUID,
    payload: DepartmentRestoreRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.restore_department(db, current_admin, department_id)


@router.delete("/departments/{department_id}", response_model=DepartmentResponse)
async def delete_department(
    department_id: uuid.UUID,
    payload: DepartmentDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.delete_department(db, current_admin, department_id)


@router.post(
    "/academic-levels/{academic_level_id}/departments",
    response_model=AcademicLevelDepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_department(
    academic_level_id: uuid.UUID,
    payload: AcademicLevelDepartmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    return await DepartmentPoolService.attach_to_level(
        db, current_admin, academic_level_id, payload
    )


@router.get(
    "/academic-levels/{academic_level_id}/departments",
    response_model=list[AcademicLevelDepartmentResponse],
)
async def list_level_departments(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
):
    return await DepartmentPoolService.list_for_level(
        db,
        current_admin,
        academic_level_id,
        active_only=active_only,
        include_archived=include_archived,
    )


@router.post(
    "/academic-levels/{academic_level_id}/departments/{link_id}/activate",
    response_model=AcademicLevelDepartmentResponse,
)
async def activate_level_department(
    academic_level_id: uuid.UUID,
    link_id: uuid.UUID,
    payload: AcademicLevelDepartmentActivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.activate_level_department(
        db, current_admin, academic_level_id, link_id
    )


@router.post(
    "/academic-levels/{academic_level_id}/departments/{link_id}/deactivate",
    response_model=AcademicLevelDepartmentResponse,
)
async def deactivate_level_department(
    academic_level_id: uuid.UUID,
    link_id: uuid.UUID,
    payload: AcademicLevelDepartmentDeactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.deactivate_level_department(
        db, current_admin, academic_level_id, link_id
    )


@router.post(
    "/academic-levels/{academic_level_id}/departments/{link_id}/archive",
    response_model=AcademicLevelDepartmentResponse,
)
async def archive_level_department(
    academic_level_id: uuid.UUID,
    link_id: uuid.UUID,
    payload: AcademicLevelDepartmentArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.archive_level_department(
        db, current_admin, academic_level_id, link_id
    )


@router.post(
    "/academic-levels/{academic_level_id}/departments/{link_id}/restore",
    response_model=AcademicLevelDepartmentResponse,
)
async def restore_level_department(
    academic_level_id: uuid.UUID,
    link_id: uuid.UUID,
    payload: AcademicLevelDepartmentRestoreRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.restore_level_department(
        db, current_admin, academic_level_id, link_id
    )


@router.delete(
    "/academic-levels/{academic_level_id}/departments/{link_id}",
    response_model=AcademicLevelDepartmentResponse,
)
async def delete_level_department(
    academic_level_id: uuid.UUID,
    link_id: uuid.UUID,
    payload: AcademicLevelDepartmentDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
):
    _ = payload.confirmation
    return await DepartmentPoolService.delete_level_department(
        db, current_admin, academic_level_id, link_id
    )
