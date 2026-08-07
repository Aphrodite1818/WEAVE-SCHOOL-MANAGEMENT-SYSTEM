# ====================================== #
#       tenant_management/router.py      #
# ====================================== #

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.core.exceptions import ForbiddenException
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.models import Tenant
from app.tenant_management.registration_service import TenantRegistrationService
from app.tenant_management.schemas import (
    TenantManagementResponse,
    TenantRegisterRequest,
    TenantUpdate,
)
from app.tenant_management.service import TenantService

router = APIRouter(tags=["Tenants"])
CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent,
    Depends(get_current_tenant_member),
]


def verify_tenant_admin_owns_tenant(
    current_admin: TenantAdmin,
    tenant_id: uuid.UUID,
) -> None:
    """Ensure a tenant admin can only manage actors in their own tenant."""

    if current_admin.tenant_id != tenant_id:
        raise ForbiddenException("You do not have access to this tenant's resources")


@router.post(
    "/register",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new school tenant",
)
async def register_tenant(
    payload: TenantRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict | JSONResponse:
    """Perform register tenant."""
    result = await TenantRegistrationService.register_tenant(
        db,
        payload,
        background_tasks=background_tasks,
    )

    if result.get("created") is False:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=jsonable_encoder(result),
            background=background_tasks,
        )

    return result


@router.get(
    "/{tenant_id}",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_200_OK,
    summary="Get tenant details by ID",
)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: DbSession,
    current_actor: CurrentTenantMember,
) -> Tenant:
    """Return tenant."""
    if current_actor.tenant_id != tenant_id:
        raise ForbiddenException("You do not have access to this tenant's resources")
    if not isinstance(current_actor, (TenantAdmin, Teacher)):
        raise ForbiddenException(
            "Operation not permitted. Required roles: admin, teacher"
        )

    return await TenantService.get_tenant_by_id(db, tenant_id)


@router.patch(
    "/{tenant_id}",
    response_model=TenantManagementResponse,
    status_code=status.HTTP_200_OK,
    summary="Update tenant profile",
)
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> Tenant:
    """Update tenant."""
    verify_tenant_admin_owns_tenant(current_admin, tenant_id)

    return await TenantService.update_tenant_profile(
        db,
        tenant_id,
        payload,
    )
