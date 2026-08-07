from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_onboarded_student,
    get_current_parent,
    get_current_superadmin,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.modules.metrics.schemas import DashboardMetricsResponse
from app.modules.metrics.service import MetricsService
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/metrics", tags=["Metrics"])

CurrentSuperadmin: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]
CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_onboarded_student)]


@router.get("/superadmin/dashboard", response_model=DashboardMetricsResponse)
async def get_superadmin_dashboard_metrics(
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> DashboardMetricsResponse:
    return await MetricsService.superadmin_dashboard(db)


@router.get("/tenant-admin/dashboard", response_model=DashboardMetricsResponse)
async def get_tenant_admin_dashboard_metrics(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> DashboardMetricsResponse:
    return await MetricsService.tenant_admin_dashboard(
        db,
        current_admin.tenant_id,
    )


@router.get("/teacher/dashboard", response_model=DashboardMetricsResponse)
async def get_teacher_dashboard_metrics(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> DashboardMetricsResponse:
    return await MetricsService.teacher_dashboard(
        db,
        teacher_id=current_teacher.id,
        tenant_id=current_teacher.tenant_id,
    )


@router.get("/parent/dashboard", response_model=DashboardMetricsResponse)
async def get_parent_dashboard_metrics(
    db: DbSession,
    current_parent: CurrentParent,
) -> DashboardMetricsResponse:
    return await MetricsService.parent_dashboard(
        db,
        current_parent,
    )


@router.get("/student/dashboard", response_model=DashboardMetricsResponse)
async def get_student_dashboard_metrics(
    db: DbSession,
    current_student: CurrentStudent,
) -> DashboardMetricsResponse:
    return await MetricsService.student_dashboard(
        db,
        current_student,
    )
