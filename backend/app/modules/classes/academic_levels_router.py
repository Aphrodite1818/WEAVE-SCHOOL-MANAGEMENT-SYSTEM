import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin, get_current_tenant_member
from app.modules.classes.schemas import (
    AcademicLevelCreate,
    AcademicLevelProgressionConfigureRequest,
    AcademicLevelProgressionResponse,
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


@router.post("", response_model=AcademicLevelResponse, status_code=status.HTTP_201_CREATED)
async def create_academic_level(
    payload: AcademicLevelCreate, db: DbSession, current_user: CurrentTenantAdmin
) -> AcademicLevelResponse:
    return await AcademicLevelService.create(db, current_user, payload)


@router.get("", response_model=list[AcademicLevelResponse])
async def list_academic_levels(
    db: DbSession,
    current_user: CurrentTenantMember,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> list[AcademicLevelResponse]:
    return await AcademicLevelService.list(
        db,
        current_user,
        active_only=active_only,
        include_archived=include_archived,
    )


@router.patch("/{academic_level_id}", response_model=AcademicLevelResponse)
async def update_academic_level(
    academic_level_id: uuid.UUID,
    payload: AcademicLevelUpdate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> AcademicLevelResponse:
    return await AcademicLevelService.update(db, current_user, academic_level_id, payload)


@router.put("/{academic_level_id}/progression", response_model=AcademicLevelProgressionResponse)
async def configure_academic_level_progression(
    academic_level_id: uuid.UUID,
    payload: AcademicLevelProgressionConfigureRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> AcademicLevelProgressionResponse:
    return await AcademicLevelService.configure_progression(
        db, current_user, academic_level_id, payload
    )
