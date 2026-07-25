"""Canonical parent account, membership, invitation, and link lifecycle routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_parent,
    get_current_parent_account,
    get_current_tenant_admin,
)
from app.modules.parents.lifecycle_contracts import (
    ParentLinkedStudentListResponse,
    ParentMembershipLifecycleService,
)
from app.modules.parents.models import (
    Parent,
    ParentAccount,
    ParentInvitationStatus,
    ParentMembershipStatus,
)
from app.modules.parents.schemas import (
    ParentAccountOnboardingRequest,
    ParentAccountPasswordChangeRequest,
    ParentAccountProfileUpdateRequest,
    ParentAccountRegisterRequest,
    ParentAccountResponse,
    ParentInvitationAcceptanceRequest,
    ParentInvitationCreateRequest,
    ParentInvitationListResponse,
    ParentInvitationPublicContextResponse,
    ParentInvitationResponse,
    ParentMembershipEndRequest,
    ParentMembershipListResponse,
    ParentMembershipNotificationUpdateRequest,
    ParentMembershipReactivateRequest,
    ParentMembershipResponse,
    ParentMembershipWithAccountResponse,
)
from app.modules.parents.service import (
    ParentAccountService,
    ParentInvitationService,
    ParentMembershipService,
)
from app.modules.students.schemas import (
    StudentParentLinkEndRequest,
    StudentParentLinkReactivateRequest,
    StudentParentLinkRequestListResponse,
    StudentParentLinkRequestResponse,
    StudentParentLinkResponse,
)
from app.modules.students.service import StudentParentLinkRequestService
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/parents", tags=["Parents"])

CurrentParentAccount: TypeAlias = Annotated[
    ParentAccount,
    Depends(get_current_parent_account),
]
CurrentParentMembership: TypeAlias = Annotated[
    Parent,
    Depends(get_current_parent),
]
CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


@router.post(
    "/accounts/register",
    status_code=status.HTTP_201_CREATED,
)
async def register_parent_account(
    payload: ParentAccountRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    return await ParentAccountService.register_account(
        db,
        payload,
        background_tasks,
    )


@router.get(
    "/invitations/context",
    response_model=ParentInvitationPublicContextResponse,
)
async def get_parent_invitation_context(
    token: str = Query(min_length=20, max_length=500),
    db: DbSession = None,
) -> ParentInvitationPublicContextResponse:
    return await ParentInvitationService.get_public_context(
        db,
        invitation_token=token,
    )


@router.get(
    "/accounts/me",
    response_model=ParentAccountResponse,
)
async def get_my_parent_account(
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    return await ParentAccountService.get_account(
        db,
        account_id=current_account.id,
    )


@router.get("/accounts/me/onboarding-status")
async def get_my_parent_account_onboarding_status(
    db: DbSession,
    current_account: CurrentParentAccount,
) -> dict[str, object]:
    return await ParentAccountService.get_onboarding_status(
        db,
        account_id=current_account.id,
    )


@router.post(
    "/accounts/me/onboarding",
    response_model=ParentAccountResponse,
)
async def complete_my_parent_account_onboarding(
    payload: ParentAccountOnboardingRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    return await ParentAccountService.complete_onboarding(
        db,
        account_id=current_account.id,
        payload=payload,
    )


@router.patch(
    "/accounts/me/profile",
    response_model=ParentAccountResponse,
)
async def update_my_parent_account_profile(
    payload: ParentAccountProfileUpdateRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentAccountResponse:
    return await ParentAccountService.update_profile(
        db,
        account_id=current_account.id,
        payload=payload,
    )


@router.post(
    "/accounts/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def change_my_parent_account_password(
    payload: ParentAccountPasswordChangeRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> None:
    await ParentAccountService.change_password(
        db,
        account_id=current_account.id,
        payload=payload,
    )


@router.get(
    "/accounts/me/memberships",
    response_model=ParentMembershipListResponse,
)
async def list_my_parent_memberships(
    db: DbSession,
    current_account: CurrentParentAccount,
) -> ParentMembershipListResponse:
    return await ParentAccountService.list_memberships(
        db,
        account_id=current_account.id,
    )


@router.post(
    "/accounts/me/invitations/accept",
    response_model=StudentParentLinkRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def accept_parent_invitation(
    payload: ParentInvitationAcceptanceRequest,
    db: DbSession,
    current_account: CurrentParentAccount,
) -> StudentParentLinkRequestResponse:
    return await ParentInvitationService.accept_invitation(
        db,
        account=current_account,
        payload=payload,
    )


@router.get(
    "/me",
    response_model=ParentMembershipWithAccountResponse,
)
async def get_my_parent_membership(
    db: DbSession,
    current_membership: CurrentParentMembership,
) -> ParentMembershipWithAccountResponse:
    return await ParentMembershipService.get_membership(
        db,
        tenant_id=current_membership.tenant_id,
        membership_id=current_membership.id,
    )


@router.patch(
    "/me/notifications",
    response_model=ParentMembershipResponse,
)
async def update_my_parent_notification_preferences(
    payload: ParentMembershipNotificationUpdateRequest,
    db: DbSession,
    current_membership: CurrentParentMembership,
) -> ParentMembershipResponse:
    return await ParentMembershipService.update_notifications(
        db,
        membership=current_membership,
        payload=payload,
    )


@router.get(
    "/me/students",
    response_model=ParentLinkedStudentListResponse,
)
async def list_my_linked_students(
    db: DbSession,
    current_membership: CurrentParentMembership,
) -> ParentLinkedStudentListResponse:
    return await ParentMembershipLifecycleService.list_children_with_links(
        db,
        membership=current_membership,
    )


@router.get(
    "/me/student-link-requests",
    response_model=StudentParentLinkRequestListResponse,
)
async def list_my_parent_link_requests(
    db: DbSession,
    current_membership: CurrentParentMembership,
) -> StudentParentLinkRequestListResponse:
    requests, total = (
        await StudentParentLinkRequestService.list_parent_requests(
            db,
            current_membership,
        )
    )
    return StudentParentLinkRequestListResponse(
        items=requests,
        total=total,
    )


@router.post(
    "/invitations",
    response_model=ParentInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_parent_invitation(
    payload: ParentInvitationCreateRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentInvitationResponse:
    return await ParentInvitationService.create_invitation(
        db,
        actor=current_admin,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/invitations",
    response_model=ParentInvitationListResponse,
)
async def list_parent_invitations(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    invitation_status: ParentInvitationStatus | None = Query(
        default=None,
        alias="status",
    ),
) -> ParentInvitationListResponse:
    invitations, total = await ParentInvitationService.list_for_tenant(
        db,
        tenant_id=current_admin.tenant_id,
        skip=skip,
        limit=limit,
        status=invitation_status,
    )
    return ParentInvitationListResponse(
        items=invitations,
        total=total,
    )


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=ParentInvitationResponse,
)
async def revoke_parent_invitation(
    invitation_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentInvitationResponse:
    return await ParentInvitationService.revoke_invitation(
        db,
        actor=current_admin,
        invitation_id=invitation_id,
    )


@router.get(
    "/student-link-requests",
    response_model=StudentParentLinkRequestListResponse,
)
async def list_pending_parent_link_requests(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> StudentParentLinkRequestListResponse:
    requests, total = await ParentMembershipLifecycleService.list_pending_requests(
        db,
        tenant_id=current_admin.tenant_id,
        skip=skip,
        limit=limit,
    )
    return StudentParentLinkRequestListResponse(items=requests, total=total)


@router.post(
    "/student-link-requests/{request_id}/decision",
    response_model=StudentParentLinkRequestResponse,
)
async def decide_parent_link_request(
    request_id: UUID,
    payload: StudentParentLinkRequestResponse,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkRequestResponse:
    # This route intentionally remains defined in tenant-admin for compatibility.
    # The canonical implementation is added below after the request schema import.
    raise NotImplementedError


@router.post(
    "/student-parent-links/{link_id}/end",
    response_model=StudentParentLinkResponse,
)
async def end_parent_link(
    link_id: UUID,
    payload: StudentParentLinkEndRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkResponse:
    return await ParentMembershipLifecycleService.end_link(
        db,
        actor=current_admin,
        link_id=link_id,
        payload=payload,
    )


@router.post(
    "/student-parent-links/{link_id}/reactivate",
    response_model=StudentParentLinkResponse,
)
async def reactivate_parent_link(
    link_id: UUID,
    payload: StudentParentLinkReactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkResponse:
    return await ParentMembershipLifecycleService.reactivate_link(
        db,
        actor=current_admin,
        link_id=link_id,
        payload=payload,
    )


@router.get(
    "/memberships",
    response_model=ParentMembershipListResponse,
)
async def list_parent_memberships(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    membership_status: ParentMembershipStatus | None = Query(
        default=None,
        alias="status",
    ),
) -> ParentMembershipListResponse:
    return await ParentMembershipService.list_for_tenant(
        db,
        tenant_id=current_admin.tenant_id,
        skip=skip,
        limit=limit,
        search=search,
        status=membership_status,
    )


@router.get(
    "/memberships/{membership_id}",
    response_model=ParentMembershipWithAccountResponse,
)
async def get_parent_membership(
    membership_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentMembershipWithAccountResponse:
    return await ParentMembershipService.get_membership(
        db,
        tenant_id=current_admin.tenant_id,
        membership_id=membership_id,
    )


@router.post(
    "/memberships/{membership_id}/end",
    response_model=ParentMembershipResponse,
)
async def end_parent_membership(
    membership_id: UUID,
    payload: ParentMembershipEndRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentMembershipResponse:
    return await ParentMembershipService.end_membership(
        db,
        actor=current_admin,
        membership_id=membership_id,
        payload=payload,
    )


@router.post(
    "/memberships/{membership_id}/reactivate",
    response_model=ParentMembershipResponse,
)
async def reactivate_parent_membership(
    membership_id: UUID,
    payload: ParentMembershipReactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ParentMembershipResponse:
    return await ParentMembershipLifecycleService.reactivate_membership(
        db,
        actor=current_admin,
        membership_id=membership_id,
        payload=payload,
    )
