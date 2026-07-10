"""Tenant branding API routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.tenant_branding.schemas import (
    TenantBrandingEffectiveResponse,
    TenantBrandingResponse,
    TenantBrandingUpdate,
)
from app.modules.tenant_branding.service import TenantBrandingService


router = APIRouter(
    prefix="/branding",
    tags=["Tenant Branding"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent,
    Depends(get_current_tenant_member),
]


@router.get(
    "",
    response_model=TenantBrandingResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tenant_branding(
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> TenantBrandingResponse:
    """Return the current tenant admin branding configuration."""

    return await TenantBrandingService.get_admin_branding(
        db=db,
        actor=current_user,
    )


@router.get(
    "/effective",
    response_model=TenantBrandingEffectiveResponse,
    status_code=status.HTTP_200_OK,
)
async def get_effective_tenant_branding(
    db: DbSession,
    current_user: CurrentTenantMember,
) -> TenantBrandingEffectiveResponse:
    """Return the effective workspace branding for the authenticated tenant actor."""

    return await TenantBrandingService.get_effective_tenant_branding(
        db=db,
        actor=current_user,
    )


@router.put(
    "",
    response_model=TenantBrandingResponse,
    status_code=status.HTTP_200_OK,
)
@router.patch(
    "",
    response_model=TenantBrandingResponse,
    status_code=status.HTTP_200_OK,
)
async def update_tenant_branding(
    payload: TenantBrandingUpdate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> TenantBrandingResponse:
    """Create or update the tenant's branding configuration."""

    return await TenantBrandingService.update_tenant_branding(
        db=db,
        actor=current_user,
        payload=payload,
    )


@router.post(
    "/enable",
    response_model=TenantBrandingResponse,
    status_code=status.HTTP_200_OK,
)
async def enable_tenant_branding(
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> TenantBrandingResponse:
    """Enable tenant branding for the current tenant."""

    return await TenantBrandingService.update_tenant_branding(
        db=db,
        actor=current_user,
        payload=TenantBrandingUpdate(is_enabled=True),
    )


@router.post(
    "/disable",
    response_model=TenantBrandingResponse,
    status_code=status.HTTP_200_OK,
)
async def disable_tenant_branding(
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> TenantBrandingResponse:
    """Disable tenant branding for the current tenant."""

    return await TenantBrandingService.update_tenant_branding(
        db=db,
        actor=current_user,
        payload=TenantBrandingUpdate(is_enabled=False),
    )
