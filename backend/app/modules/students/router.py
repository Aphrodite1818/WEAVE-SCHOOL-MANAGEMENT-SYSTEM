"""Canonical student self-service and tenant-member read routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_onboarded_student,
    get_current_student,
    get_current_tenant_member,
)
from app.modules.parents.models import Parent
from app.modules.students.models import AcademicStatus, Student
from app.modules.students.read_service import StudentReadService
from app.modules.students.schemas import (
    StudentChangePasswordRequest,
    StudentDetailResponse,
    StudentListResponse,
    StudentOnboardingStatusResponse,
    StudentOnboardingUpdate,
    StudentParentLinkListResponse,
    StudentParentLinkRequestDecision,
    StudentParentLinkRequestListResponse,
    StudentParentLinkRequestResponse,
    StudentResponse,
    StudentSelfUpdate,
)
from app.modules.students.service import (
    StudentAccessCodeService,
    StudentParentLinkRequestService,
    StudentParentLinkService,
    StudentService,
)
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(tags=["Students"])

CurrentStudent: TypeAlias = Annotated[
    Student,
    Depends(get_current_student),
]
CurrentOnboardedStudent: TypeAlias = Annotated[
    Student,
    Depends(get_current_onboarded_student),
]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Parent | Student,
    Depends(get_current_tenant_member),
]
CurrentStudentListActor: TypeAlias = Annotated[
    TenantAdmin | Teacher | Parent,
    Depends(get_current_tenant_member),
]


@router.get("", response_model=StudentListResponse)
async def list_students(
    db: DbSession,
    current_user: CurrentStudentListActor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    class_id: UUID | None = Query(default=None),
    status_filter: AcademicStatus | None = Query(
        default=None,
        alias="status",
    ),
) -> StudentListResponse:
    """List students visible to the current tenant actor."""

    students, total = await StudentReadService.list_students(
        db,
        current_user,
        skip=skip,
        limit=limit,
        search=search,
        class_id=class_id,
        status=status_filter,
    )
    return StudentListResponse(items=students, total=total)


@router.get("/me", response_model=StudentDetailResponse)
async def get_my_student_profile(
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentDetailResponse:
    return await StudentService.get_my_student_profile(
        db,
        current_user,
    )


@router.patch("/me/profile", response_model=StudentDetailResponse)
async def update_my_student_profile(
    payload: StudentSelfUpdate,
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentDetailResponse:
    return await StudentService.update_my_student_profile(
        db,
        current_user,
        payload,
    )


@router.post("/me/onboarding", response_model=StudentDetailResponse)
async def complete_my_student_onboarding(
    payload: StudentOnboardingUpdate,
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentDetailResponse:
    return await StudentService.update_my_student_profile(
        db,
        current_user,
        payload,
    )


@router.get(
    "/me/onboarding-status",
    response_model=StudentOnboardingStatusResponse,
)
async def get_my_student_onboarding_status(
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentOnboardingStatusResponse:
    return await StudentService.get_my_onboarding_status(
        db,
        current_user,
    )


@router.post("/me/change-password", response_model=StudentResponse)
async def change_my_student_password(
    payload: StudentChangePasswordRequest,
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentResponse:
    return await StudentAccessCodeService.change_password(
        db,
        actor=current_user,
        payload=payload,
    )


@router.get(
    "/me/parent-link-requests",
    response_model=StudentParentLinkRequestListResponse,
)
async def list_my_parent_link_requests(
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkRequestListResponse:
    requests, total = await StudentParentLinkRequestService.list_student_requests(
        db,
        current_user,
    )
    return StudentParentLinkRequestListResponse(
        items=requests,
        total=total,
    )


@router.post(
    "/me/parent-link-requests/{request_id}/decision",
    response_model=StudentParentLinkRequestResponse,
)
async def decide_parent_link_request(
    request_id: UUID,
    payload: StudentParentLinkRequestDecision,
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkRequestResponse:
    return await StudentParentLinkRequestService.respond_to_request(
        db,
        current_user,
        request_id,
        payload,
    )


@router.get(
    "/me/parent-links",
    response_model=StudentParentLinkListResponse,
)
async def list_my_parent_links(
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkListResponse:
    links, total = await StudentParentLinkService.list_my_parent_links(
        db,
        current_user,
    )
    return StudentParentLinkListResponse(items=links, total=total)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student_profile(
    student_id: UUID,
    db: DbSession,
    current_user: CurrentTenantMember,
) -> StudentResponse:
    if isinstance(current_user, Student) and current_user.id != student_id:
        # Student self-access is intentionally limited to /me.
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("Students cannot view another student's profile.")
    return await StudentService.get_student_profile(
        db,
        current_user,
        student_id,
    )
