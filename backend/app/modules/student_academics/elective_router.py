from __future__ import annotations

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_student, get_current_tenant_admin
from app.modules.student_academics.elective_schemas import (
    ElectiveGroupCreate,
    ElectiveGroupResponse,
    ElectiveGroupUpdate,
    StudentElectiveSelectionUpdate,
    StudentElectiveWorkspaceResponse,
)
from app.modules.student_academics.elective_service import ElectivePolicyService
from app.modules.students.models import Student
from app.modules.tenant_admins.models import TenantAdmin


admin_router = APIRouter(
    prefix="/tenant-admin/academics",
    tags=["Curriculum Electives"],
)
student_router = APIRouter(
    prefix="/students/academics",
    tags=["Student Electives"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]


@admin_router.get(
    "/levels/{academic_level_id}/elective-groups",
    response_model=list[ElectiveGroupResponse],
)
async def list_elective_groups(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> list[ElectiveGroupResponse]:
    return await ElectivePolicyService.list_groups(
        db,
        tenant_id=current_admin.tenant_id,
        academic_level_id=academic_level_id,
    )


@admin_router.post(
    "/levels/{academic_level_id}/elective-groups",
    response_model=ElectiveGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_elective_group(
    academic_level_id: uuid.UUID,
    payload: ElectiveGroupCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ElectiveGroupResponse:
    return await ElectivePolicyService.create_group(
        db,
        tenant_id=current_admin.tenant_id,
        academic_level_id=academic_level_id,
        payload=payload,
    )


@admin_router.patch(
    "/elective-groups/{elective_group_id}",
    response_model=ElectiveGroupResponse,
)
async def update_elective_group(
    elective_group_id: uuid.UUID,
    payload: ElectiveGroupUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ElectiveGroupResponse:
    return await ElectivePolicyService.update_group(
        db,
        tenant_id=current_admin.tenant_id,
        elective_group_id=elective_group_id,
        payload=payload,
    )


@admin_router.post(
    "/elective-groups/{elective_group_id}/archive",
    response_model=ElectiveGroupResponse,
)
async def archive_elective_group(
    elective_group_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ElectiveGroupResponse:
    return await ElectivePolicyService.archive_group(
        db,
        tenant_id=current_admin.tenant_id,
        elective_group_id=elective_group_id,
    )


@admin_router.post(
    "/elective-groups/{elective_group_id}/restore",
    response_model=ElectiveGroupResponse,
)
async def restore_elective_group(
    elective_group_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ElectiveGroupResponse:
    return await ElectivePolicyService.restore_group(
        db,
        tenant_id=current_admin.tenant_id,
        elective_group_id=elective_group_id,
    )


@student_router.get(
    "/electives",
    response_model=StudentElectiveWorkspaceResponse,
)
async def get_my_elective_workspace(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentElectiveWorkspaceResponse:
    return await ElectivePolicyService.get_student_workspace(
        db,
        student=current_student,
    )


@student_router.put(
    "/electives/{elective_group_id}",
    response_model=StudentElectiveWorkspaceResponse,
)
async def replace_my_elective_selection(
    elective_group_id: uuid.UUID,
    payload: StudentElectiveSelectionUpdate,
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentElectiveWorkspaceResponse:
    return await ElectivePolicyService.replace_student_selection(
        db,
        student=current_student,
        elective_group_id=elective_group_id,
        payload=payload,
    )
