"""Dev-test routes for global parent and teacher account flows."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_parent_account,
    get_current_teacher_account,
)
from app.modules.parents.models import ParentAccount
from app.modules.parents.schemas import (
    ParentAccountOnboardingRequest,
    ParentAccountProfileUpdateRequest,
    ParentAccountRegisterRequest,
    ParentAccountResponse,
)
from app.modules.parents.service import ParentAccountService
from app.modules.teachers.models import TeacherAccount
from app.modules.teachers.schemas import (
    TeacherAccountOnboardingRequest,
    TeacherAccountProfileUpdateRequest,
    TeacherAccountRegisterRequest,
    TeacherAccountResponse,
)
from app.modules.teachers.service import TeacherAccountService


router = APIRouter(tags=["Global Account Flows"])

CurrentParentAccount: TypeAlias = Annotated[
    ParentAccount,
    Depends(get_current_parent_account),
]
CurrentTeacherAccount: TypeAlias = Annotated[
    TeacherAccount,
    Depends(get_current_teacher_account),
]


@router.post(
    "/parents/accounts/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a global parent account",
)
async def register_parent_account(
    payload: ParentAccountRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict:
    return await ParentAccountService.register_account(
        db=db,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/parents/accounts/me/onboarding-status",
    summary="Get my global parent account onboarding status",
)
async def get_parent_account_onboarding_status(
    db: DbSession,
    current_account: CurrentParentAccount,
) -> dict:
    return await ParentAccountService.get_onboarding_status(
        db=db,
        account_id=current_account.id,
    )


@router.post(
    "/parents/accounts/me/onboarding",
    response_model=ParentAccountResponse,
    summary="Complete my global parent account onboarding",
)
async def complete_parent_account_onboarding(
    payload: ParentAccountOnboardingRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    return await ParentAccountService.complete_onboarding(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


@router.patch(
    "/parents/accounts/me/profile",
    response_model=ParentAccountResponse,
    summary="Update my global parent account profile",
)
async def update_parent_account_profile(
    payload: ParentAccountProfileUpdateRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    return await ParentAccountService.update_profile(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


@router.post(
    "/teachers/accounts/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a global teacher account",
)
async def register_teacher_account(
    payload: TeacherAccountRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict:
    return await TeacherAccountService.register_account(
        db=db,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/teachers/accounts/me/onboarding-status",
    summary="Get my global teacher account onboarding status",
)
async def get_teacher_account_onboarding_status(
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> dict:
    return await TeacherAccountService.get_onboarding_status(
        db=db,
        account_id=current_account.id,
    )


@router.post(
    "/teachers/accounts/me/onboarding",
    response_model=TeacherAccountResponse,
    summary="Complete my global teacher account onboarding",
)
async def complete_teacher_account_onboarding(
    payload: TeacherAccountOnboardingRequest,
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> TeacherAccountResponse:
    return await TeacherAccountService.complete_onboarding(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


@router.patch(
    "/teachers/accounts/me/profile",
    response_model=TeacherAccountResponse,
    summary="Update my global teacher account profile",
)
async def update_teacher_account_profile(
    payload: TeacherAccountProfileUpdateRequest,
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> TeacherAccountResponse:
    return await TeacherAccountService.update_profile(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )
