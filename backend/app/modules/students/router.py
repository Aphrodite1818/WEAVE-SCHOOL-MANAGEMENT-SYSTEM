from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.config.security import hash_password
from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_onboarded_student,
    get_current_parent,
    get_current_student,
    get_current_tenant_member,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.utils.validators import validate_password_strength
from app.modules.parents.models import Parent
from app.modules.students.models import AcademicStatus, Student
from app.modules.students.repository import StudentAccessCodeRepository, StudentRepository
from app.modules.students.schemas import (
    StudentChangePasswordRequest,
    StudentLinkCodeRedeem,
    StudentListResponse,
    StudentOnboardingStatusResponse,
    StudentOnboardingUpdate,
    StudentParentLinkRequestListResponse,
    StudentParentLinkRequestRespond,
    StudentParentLinkRequestResponse,
    StudentParentLinkListResponse,
    StudentParentLinkResponse,
    StudentResponse,
)
from app.modules.students.service import (
    StudentLinkCodeService,
    StudentParentLinkService,
    StudentParentLinkRequestService,
    StudentService,
)
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(tags=["Students"])

CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]
CurrentOnboardedStudent: TypeAlias = Annotated[
    Student,
    Depends(get_current_onboarded_student),
]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]
CurrentStudentViewer: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent,
    Depends(get_current_tenant_member),
]
CurrentStudentListActor: TypeAlias = Annotated[
    TenantAdmin | Teacher | Parent,
    Depends(get_current_tenant_member),
]


@router.get(
    "",
    response_model=StudentListResponse,
    summary="List students",
)
async def list_students(
    db: DbSession,
    current_user: CurrentStudentListActor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    class_id: UUID | None = Query(default=None),
    status_filter: AcademicStatus | None = Query(default=None, alias="status"),
) -> StudentListResponse:
    """List student profiles."""

    students, total = await StudentService.list_students(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        search=search,
        class_id=class_id,
        status=status_filter,
    )
    return StudentListResponse(items=students, total=total)


@router.get(
    "/me",
    response_model=StudentResponse,
    summary="Get my student profile",
)
async def get_my_student_profile(
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentResponse:
    """Get the logged-in student's profile."""

    return await StudentService.get_my_student_profile(
        db=db,
        actor=current_user,
    )


@router.patch(
    "/me/profile",
    response_model=StudentResponse,
    summary="Update my student profile",
)
async def update_my_student_profile(
    payload: StudentOnboardingUpdate,
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentResponse:
    """Allow the logged-in student to update self-service profile fields."""

    return await StudentService.update_my_student_profile(
        db=db,
        actor=current_user,
        payload=payload,
    )


@router.post(
    "/me/change-password",
    response_model=StudentResponse,
    summary="Set my student password",
)
async def change_my_student_password(
    payload: StudentChangePasswordRequest,
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentResponse:
    """Allow the logged-in student to set a new password using an access code."""

    StudentService._ensure_student_actor(current_user)

    student = await StudentRepository.get_student_by_id(
        db=db,
        tenant_id=current_user.tenant_id,
        student_id=current_user.id,
    )
    if student is None:
        raise NotFoundException(detail="Student profile not found")

    if payload.new_password != payload.confirm_password:
        raise BadRequestException(detail="New password and confirmation do not match")

    access_code_is_valid = await StudentService._student_access_code_is_valid(
        db=db,
        student=student,
        plain_code=payload.access_code,
    )
    if not access_code_is_valid:
        raise BadRequestException(detail="Access code is incorrect")

    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise BadRequestException(detail=str(exc)) from exc

    student.password_hash = hash_password(payload.new_password)
    student.password_reset_required = False

    await StudentAccessCodeRepository.mark_all_codes_used(
        db=db,
        tenant_id=student.tenant_id,
        student_id=student.id,
    )

    updated_student = await StudentRepository.save(db=db, student=student)
    await db.commit()
    await db.refresh(updated_student)

    return StudentResponse.model_validate(updated_student)


@router.get(
    "/me/onboarding-status",
    response_model=StudentOnboardingStatusResponse,
    summary="Get my student onboarding status",
)
async def get_my_student_onboarding_status(
    db: DbSession,
    current_user: CurrentStudent,
) -> StudentOnboardingStatusResponse:
    """Return the current student onboarding status."""

    return await StudentService.get_my_onboarding_status(
        db=db,
        actor=current_user,
    )


@router.get(
    "/me/parent-link-requests",
    response_model=StudentParentLinkRequestListResponse,
    summary="Get my pending parent link requests",
)
async def get_my_parent_link_requests(
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkRequestListResponse:
    """Get pending parent link requests for the logged-in student."""

    requests, total = await StudentParentLinkRequestService.list_student_requests(
        db=db,
        actor=current_user,
    )
    return StudentParentLinkRequestListResponse(items=requests, total=total)


@router.post(
    "/me/parent-link-requests/{request_id}/respond",
    response_model=StudentParentLinkRequestResponse,
    summary="Respond to a parent link request",
)
async def respond_to_parent_link_request(
    request_id: UUID,
    payload: StudentParentLinkRequestRespond,
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkRequestResponse:
    """Allow the logged-in student to approve or reject a pending request."""

    return await StudentParentLinkRequestService.respond_to_request(
        db=db,
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )


@router.get(
    "/me/parent-links",
    response_model=StudentParentLinkListResponse,
    summary="Get my parent links",
)
async def get_my_parent_links(
    db: DbSession,
    current_user: CurrentOnboardedStudent,
) -> StudentParentLinkListResponse:
    """Get parent links for the logged-in student."""

    links, total = await StudentParentLinkService.list_my_parent_links(
        db=db,
        actor=current_user,
    )
    return StudentParentLinkListResponse(items=links, total=total)


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Get a student profile",
)
async def get_student_profile(
    student_id: UUID,
    db: DbSession,
    current_user: CurrentStudentViewer,
) -> StudentResponse:
    """Get a student profile by id."""

    return await StudentService.get_student_profile(
        db=db,
        actor=current_user,
        student_id=student_id,
    )


@router.post(
    "/link-codes/redeem",
    response_model=StudentParentLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Redeem a student link code",
)
async def redeem_student_link_code(
    payload: StudentLinkCodeRedeem,
    db: DbSession,
    current_user: CurrentParent,
) -> StudentParentLinkResponse:
    """Link the logged-in parent to a student using a pairing code."""

    return await StudentLinkCodeService.redeem_student_link_code(
        db=db,
        actor=current_user,
        payload=payload,
    )
