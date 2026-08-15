from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin, get_current_tenant_member
from app.modules.classes.schemas import DepartmentCreate, DepartmentResponse
from app.modules.classes.service import DepartmentService
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/departments", tags=["Departments"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent, Depends(get_current_tenant_member)
]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> DepartmentResponse:
    return await DepartmentService.create(db, current_admin, payload)


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    db: DbSession,
    current_member: CurrentTenantMember,
    active_only: bool = Query(default=False),
) -> list[DepartmentResponse]:
    return await DepartmentService.list(
        db, current_member, active_only=active_only
    )
