from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_parent, get_current_parent_account
from app.modules.parents.models import Parent, ParentAccount
from app.modules.parents.schemas import (
    ParentAccountOnboardingRequest,
    ParentAccountProfileUpdateRequest,
    ParentAccountRegisterRequest,
    ParentAccountResponse,
    ParentLinkedStudentListResponse,
    ParentOnboardingStatusResponse,
    ParentOnboardingUpdate,
    ParentResponse,
)
from app.modules.students.schemas import (
    StudentParentLinkRequestCreate,
    StudentParentLinkRequestListResponse,
    StudentParentLinkRequestResponse,
)
from app.modules.students.service import StudentParentLinkRequestService
from app.modules.parents.service import ParentAccountService
from app.modules.parents.tenant_service import ParentService


router = APIRouter(
    prefix="/parents",
    tags=["Parents"],
)
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]
CurrentParentAccount: TypeAlias = Annotated[
    ParentAccount,
    Depends(get_current_parent_account),
]


@router.post(
    "/accounts/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a global parent account",
)
async def register_parent_account(
    payload: ParentAccountRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict:
    """Register a global parent login account."""

    return await ParentAccountService.register_account(
        db=db,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/accounts/me/onboarding-status",
    summary="Get my global parent account onboarding status",
)
async def get_my_parent_account_onboarding_status(
    db: DbSession,
    current_account: CurrentParentAccount,
) -> dict:
    """Return onboarding state for the logged-in global parent account."""

    return await ParentAccountService.get_onboarding_status(
        db=db,
        account_id=current_account.id,
    )


@router.post(
    "/accounts/me/onboarding",
    response_model=ParentAccountResponse,
    summary="Complete my global parent account onboarding",
)
async def complete_my_parent_account_onboarding(
    payload: ParentAccountOnboardingRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    """Complete required global parent account profile fields."""

    return await ParentAccountService.complete_onboarding(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


@router.patch(
    "/accounts/me/profile",
    response_model=ParentAccountResponse,
    summary="Update my global parent account profile",
)
async def update_my_parent_account_profile(
    payload: ParentAccountProfileUpdateRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    """Update parent-controlled global account profile fields."""

    return await ParentAccountService.update_profile(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )





@router.get(
    "/me",
    response_model=ParentResponse,
    summary="Get my parent profile",
)
async def get_my_parent_profile(
    db: DbSession,
    current_user: CurrentParent,
) -> ParentResponse:
    """Get the logged-in parent's profile."""

    return await ParentService.get_my_parent_profile(
        db=db,
        actor=current_user,
    )


@router.patch(
    "/me/profile",
    response_model=ParentResponse,
    summary="Update my parent profile",
)
async def update_my_parent_profile(
    payload: ParentOnboardingUpdate,
    db: DbSession,
    current_user: CurrentParent,
) -> ParentResponse:
    """Allow the logged-in parent to update their own profile."""

    return await ParentService.update_my_parent_profile(
        db=db,
        actor=current_user,
        payload=payload,
    )


@router.get(
    "/me/onboarding-status",
    response_model=ParentOnboardingStatusResponse,
    summary="Get my parent onboarding status",
)
async def get_my_parent_onboarding_status(
    db: DbSession,
    current_user: CurrentParent,
) -> ParentOnboardingStatusResponse:
    """Return the current parent onboarding status."""

    return await ParentService.get_my_onboarding_status(
        db=db,
        actor=current_user,
    )


@router.get(
    "/me/students",
    response_model=ParentLinkedStudentListResponse,
    summary="Get my linked students",
)
async def get_my_linked_students(
    db: DbSession,
    current_user: CurrentParent,
) -> ParentLinkedStudentListResponse:
    """Get students linked to the logged-in parent."""

    students, total = await ParentService.get_my_linked_students(
        db=db,
        actor=current_user,
    )
    return ParentLinkedStudentListResponse(items=students, total=total)


@router.post(
    "/me/student-link-requests",
    response_model=StudentParentLinkRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request to link a student by admission number",
)
async def create_student_link_request(
    payload: StudentParentLinkRequestCreate,
    db: DbSession,
    current_user: CurrentParent,
) -> StudentParentLinkRequestResponse:
    """Create a pending student-link request for the logged-in parent."""

    return await StudentParentLinkRequestService.create_request(
        db=db,
        actor=current_user,
        payload=payload,
    )


@router.get(
    "/me/student-link-requests",
    response_model=StudentParentLinkRequestListResponse,
    summary="Get my student link requests",
)
async def get_my_student_link_requests(
    db: DbSession,
    current_user: CurrentParent,
) -> StudentParentLinkRequestListResponse:
    """Return student link requests submitted by the logged-in parent."""

    requests, total = await StudentParentLinkRequestService.list_parent_requests(
        db=db,
        actor=current_user,
    )
    return StudentParentLinkRequestListResponse(items=requests, total=total)

