from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_teacher,
    get_current_tenant_admin,
    get_current_superadmin,
)
from app.modules.search.schemas import TenantSearchResponse
from app.modules.search.service import TenantSearchService
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.teachers.models import Teacher
from app.modules.superadmin.models import SuperAdmin

router = APIRouter(tags=["Tenant Search"])
tenant_admin_router = APIRouter(prefix="/tenant-admin/search", tags=["Tenant Search"])
teacher_router = APIRouter(prefix="/teachers/me/search", tags=["Teacher Search"])
superadmin_router = APIRouter(prefix="/superadmin/search", tags=["Superadmin Search"])

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentSuperAdmin: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]


@tenant_admin_router.get("", response_model=TenantSearchResponse)
async def search_tenant(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> TenantSearchResponse:
    items = await TenantSearchService.search_tenant(
        db=db,
        tenant_id=current_admin.tenant_id,
        query=q,
        limit=limit,
    )
    return TenantSearchResponse(items=items, total=len(items))


@teacher_router.get("", response_model=TenantSearchResponse)
async def search_teacher(
    db: DbSession,
    current_teacher: CurrentTeacher,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> TenantSearchResponse:
    items = await TenantSearchService.search_teacher(
        db=db,
        tenant_id=current_teacher.tenant_id,
        teacher_id=current_teacher.id,
        query=q,
        limit=limit,
    )
    return TenantSearchResponse(items=items, total=len(items))


@superadmin_router.get("", response_model=TenantSearchResponse)
async def search_superadmin(
    db: DbSession,
    current_superadmin: CurrentSuperAdmin,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> TenantSearchResponse:
    items = await TenantSearchService.search_superadmin(
        db=db,
        query=q,
        limit=limit,
    )
    return TenantSearchResponse(items=items, total=len(items))


router.include_router(tenant_admin_router)
router.include_router(teacher_router)
router.include_router(superadmin_router)
