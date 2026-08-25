import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin, get_current_tenant_member
from app.modules.classes.schemas import (
    AcademicCategoryOption,
    AcademicLevelCreate,
    AcademicLevelResponse,
    AcademicLevelUpdate,
)
from app.modules.classes.service import AcademicLevelService
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/academic-levels", tags=["Academic Levels"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent, Depends(get_current_tenant_member)
]


@router.get("/categories", response_model=list[AcademicCategoryOption])
async def list_allowed_categories(db: DbSession, current_user: CurrentTenantMember):
    return await AcademicLevelService.category_options(db, current_user)


@router.post("", response_model=AcademicLevelResponse, status_code=status.HTTP_201_CREATED)
async def create_academic_level(
    payload: AcademicLevelCreate, db: DbSession, current_user: CurrentTenantAdmin
):
    return await AcademicLevelService.create(db, current_user, payload)


@router.get("", response_model=list[AcademicLevelResponse])
async def list_academic_levels(
    db: DbSession,
    current_user: CurrentTenantMember,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
):
    return await AcademicLevelService.list(
        db, current_user, active_only=active_only, include_archived=include_archived
    )


@router.patch("/{academic_level_id}", response_model=AcademicLevelResponse)
async def update_academic_level(
    academic_level_id: uuid.UUID,
    payload: AcademicLevelUpdate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.update(db, current_user, academic_level_id, payload)


@router.post("/{academic_level_id}/activate", response_model=AcademicLevelResponse)
async def activate_academic_level(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.activate(db, current_user, academic_level_id)


@router.post("/{academic_level_id}/deactivate", response_model=AcademicLevelResponse)
async def deactivate_academic_level(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.deactivate(db, current_user, academic_level_id)


@router.post("/{academic_level_id}/archive", response_model=AcademicLevelResponse)
async def archive_academic_level(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.archive(db, current_user, academic_level_id)


@router.post("/{academic_level_id}/restore", response_model=AcademicLevelResponse)
async def restore_academic_level(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.restore(db, current_user, academic_level_id)


@router.delete("/{academic_level_id}", response_model=AcademicLevelResponse)
async def delete_academic_level(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
):
    return await AcademicLevelService.delete_if_unused(db, current_user, academic_level_id)
