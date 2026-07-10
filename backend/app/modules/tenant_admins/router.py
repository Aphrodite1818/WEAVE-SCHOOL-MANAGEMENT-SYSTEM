"""Tenant-admin route boundary for tenant-scoped management."""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.parents.schemas import (
    ParentCreate,
    ParentListResponse,
    ParentResponse,
    ParentUpdate,
)
from app.modules.parents.service import ParentService
from app.modules.students.models import AcademicStatus
from app.modules.students.schemas import (
    StudentCreate,
    StudentLinkCodeCreate,
    StudentLinkCodeResponse,
    StudentListResponse,
    StudentParentLinkCreate,
    StudentParentLinkResponse,
    StudentParentLinkUpdate,
    StudentResponse,
    StudentUpdate,
    StudentAdminAccessCodeResponse
)
from app.modules.students.service import (
    StudentLinkCodeService,
    StudentParentLinkService,
    StudentService,
)
from app.modules.teachers.schemas import (
    TeacherCreate,
    TeacherListResponse,
    TeacherResponse,
    TeacherUpdate,
)
from app.modules.teachers.service import TeacherService
from app.modules.student_academics.schemas import TeacherAssignmentListResponse
from app.modules.student_academics.service import StudentAcademicService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.tenant_admins.service import TenantAdminService
from app.tenant_management.schemas import (
    TenantOnboardingStatusResponse,
    TenantOnboardingUpdate,
)
from app.tenant_management.service import TenantService


router = APIRouter()
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.get(
    "/onboarding-status",
    response_model=TenantOnboardingStatusResponse,
    summary="Get tenant-admin onboarding status",
)
async def get_tenant_admin_onboarding_status(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantOnboardingStatusResponse:
    """Return the current tenant-admin onboarding status."""

    return await TenantService.get_tenant_onboarding_status(
        db=db,
        tenant_id=current_admin.tenant_id,
    )


@router.get(
    "/analytics/overview",
    status_code=status.HTTP_200_OK,
    summary="Get tenant-admin analytics overview",
)
async def get_tenant_admin_analytics_overview(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> dict[str, object]:
    """Return analytics data for the current tenant admin dashboard."""

    return await TenantAdminService.get_analytics_overview(
        db=db,
        tenant_id=current_admin.tenant_id,
    )


@router.patch(
    "/tenant/onboarding",
    response_model=TenantOnboardingStatusResponse,
    summary="Complete tenant-admin school onboarding",
)
async def complete_tenant_admin_onboarding(
    payload: TenantOnboardingUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantOnboardingStatusResponse:
    """Update the current tenant's onboarding fields."""

    await TenantService.update_tenant_onboarding(
        db=db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
    )
    return await TenantService.get_tenant_onboarding_status(
        db=db,
        tenant_id=current_admin.tenant_id,
    )


@router.post(
    "/teachers",
    response_model=TeacherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a teacher",
)
async def create_teacher(
    payload: TeacherCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherResponse:
    """Create a teacher through the tenant-admin boundary."""

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.TEACHERS,
    )
    teacher = await TeacherService.create_teacher(
        db=db,
        actor=current_admin,
        teacher_data=payload,
        background_tasks=background_tasks,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)
    return teacher


@router.get(
    "/teachers",
    response_model=TeacherListResponse,
    summary="List teachers",
)
async def list_teachers(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
) -> TeacherListResponse:
    """List teachers for the current tenant."""

    teachers, total = await TeacherService.list_teachers(
        db=db,
        actor=current_admin,
        skip=skip,
        limit=limit,
        search=search,
    )
    return TeacherListResponse(
        items=[TeacherResponse.model_validate(teacher) for teacher in teachers],
        total=total,
    )


@router.get(
    "/teachers/{teacher_id}",
    response_model=TeacherResponse,
    summary="Get a teacher",
)
async def get_teacher(
    teacher_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherResponse:
    """Return a teacher in the current tenant."""

    return await TeacherService.get_teacher(
        db=db,
        actor=current_admin,
        teacher_id=teacher_id,
    )


@router.get(
    "/teachers/{teacher_id}/assignments",
    response_model=TeacherAssignmentListResponse,
    summary="List teacher class-subject assignments",
)
async def list_teacher_class_assignments(
    teacher_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    active_only: bool = Query(default=True),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> TeacherAssignmentListResponse:
    items, total = await StudentAcademicService.list_teacher_assignment_responses(
        db=db,
        tenant_id=current_admin.tenant_id,
        teacher_id=teacher_id,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )
    return TeacherAssignmentListResponse(items=items, total=total)


@router.patch(
    "/teachers/{teacher_id}",
    response_model=TeacherResponse,
    summary="Update a teacher",
)
async def update_teacher(
    teacher_id: UUID,
    payload: TeacherUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherResponse:
    """Update a teacher in the current tenant."""

    return await TeacherService.update_teacher(
        db=db,
        actor=current_admin,
        teacher_id=teacher_id,
        teacher_data=payload,
    )


@router.delete(
    "/teachers/{teacher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a teacher",
)
async def delete_teacher(
    teacher_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    """Archive a teacher in the current tenant."""

    await TeacherService.delete_teacher(
        db=db,
        actor=current_admin,
        teacher_id=teacher_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)


@router.post(
    "/parents",
    response_model=ParentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a parent",
)
async def create_parent(
    payload: ParentCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentResponse:
    """Create a parent through the tenant-admin boundary."""

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.PARENTS,
    )
    parent = await ParentService.create_parent(
        db=db,
        actor=current_admin,
        payload=payload,
        background_tasks=background_tasks,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)
    return parent


@router.get(
    "/parents",
    response_model=ParentListResponse,
    summary="List parents",
)
async def list_parents(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
) -> ParentListResponse:
    """List parents for the current tenant."""

    parents, total = await ParentService.get_all_parents(
        db=db,
        actor=current_admin,
        skip=skip,
        limit=limit,
        search=search,
    )
    return ParentListResponse(items=parents, total=total)


@router.get(
    "/parents/{parent_id}",
    response_model=ParentResponse,
    summary="Get a parent",
)
async def get_parent(
    parent_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentResponse:
    """Return a parent in the current tenant."""

    return await ParentService.get_parent_profile(
        db=db,
        actor=current_admin,
        parent_id=parent_id,
    )


@router.patch(
    "/parents/{parent_id}",
    response_model=ParentResponse,
    summary="Update a parent",
)
async def update_parent(
    parent_id: UUID,
    payload: ParentUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentResponse:
    """Update a parent in the current tenant."""

    return await ParentService.update_parent_profile(
        db=db,
        actor=current_admin,
        parent_id=parent_id,
        payload=payload,
    )


@router.delete(
    "/parents/{parent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a parent",
)
async def delete_parent(
    parent_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    """Delete a parent in the current tenant."""

    await ParentService.delete_parent_profile(
        db=db,
        actor=current_admin,
        parent_id=parent_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)


@router.post(
    "/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student",
)
async def create_student(
    payload: StudentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentResponse:
    """Create a student through the tenant-admin boundary."""

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    student = await StudentService.create_student_profile(
        db=db,
        actor=current_admin,
        payload=payload,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)
    return student


@router.get(
    "/students",
    response_model=StudentListResponse,
    summary="List students",
)
async def list_students(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    class_id: UUID | None = Query(default=None),
    status_filter: AcademicStatus | None = Query(default=None, alias="status"),
) -> StudentListResponse:
    """List students for the current tenant."""

    students, total = await StudentService.list_students(
        db=db,
        actor=current_admin,
        skip=skip,
        limit=limit,
        search=search,
        class_id=class_id,
        status=status_filter,
    )
    return StudentListResponse(items=students, total=total)


@router.get(
    "/students/{student_id}",
    response_model=StudentResponse,
    summary="Get a student",
)
async def get_student(
    student_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentResponse:
    """Return a student in the current tenant."""

    return await StudentService.get_student_profile(
        db=db,
        actor=current_admin,
        student_id=student_id,
    )


@router.post(
        "/students/{student_id}/reset-access-code",
        response_model = StudentAdminAccessCodeResponse,
        summary = "Generate a new student access code"
)
async def reset_student_access_code(
    student_id : UUID,
    db : DbSession,
    current_admin : CurrentTenantAdmin
) -> StudentAdminAccessCodeResponse:
    """Generate a temporary access code for student"""

    return await StudentService.admin_reset_student_access_code(
        db = db ,
        actor = current_admin,
        student_id = student_id
    )


@router.patch(
    "/students/{student_id}",
    response_model=StudentResponse,
    summary="Update a student",
)
async def update_student(
    student_id: UUID,
    payload: StudentUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentResponse:
    """Update a student in the current tenant."""

    return await StudentService.update_student_profile(
        db=db,
        actor=current_admin,
        student_id=student_id,
        payload=payload,
    )


@router.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a student",
)
async def delete_student(
    student_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    """Delete a student in the current tenant."""

    await StudentService.delete_student_profile(
        db=db,
        actor=current_admin,
        student_id=student_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)


@router.post(
    "/student-parent-links",
    response_model=StudentParentLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student-parent link",
)
async def create_student_parent_link(
    payload: StudentParentLinkCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkResponse:
    """Create a student-parent link for the current tenant."""

    return await StudentParentLinkService.create_student_parent_link(
        db=db,
        actor=current_admin,
        payload=payload,
    )


@router.patch(
    "/student-parent-links/{link_id}",
    response_model=StudentParentLinkResponse,
    summary="Update a student-parent link",
)
async def update_student_parent_link(
    link_id: UUID,
    payload: StudentParentLinkUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkResponse:
    """Update a student-parent link for the current tenant."""

    return await StudentParentLinkService.update_student_parent_link(
        db=db,
        actor=current_admin,
        link_id=link_id,
        payload=payload,
    )


@router.delete(
    "/student-parent-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a student-parent link",
)
async def delete_student_parent_link(
    link_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    """Delete a student-parent link for the current tenant."""

    await StudentParentLinkService.delete_student_parent_link(
        db=db,
        actor=current_admin,
        link_id=link_id,
    )


@router.post(
    "/student-link-codes",
    response_model=StudentLinkCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student link code",
)
async def create_student_link_code(
    payload: StudentLinkCodeCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLinkCodeResponse:
    """Create a student link code for the current tenant."""

    return await StudentLinkCodeService.create_student_link_code(
        db=db,
        actor=current_admin,
        payload=payload,
    )
