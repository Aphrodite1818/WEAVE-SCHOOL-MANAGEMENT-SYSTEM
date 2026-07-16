"""Authenticated tenant-membership selection and switching routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Request, Response

from app.config.settings import settings
from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_actor
from app.core.exceptions import ForbiddenException
from app.modules.auth.login_service import AuthService
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.router import LoginResponse, _client_ip, _set_refresh_token_cookie
from app.modules.auth.schemas import MembershipSelectionRequest
from app.modules.auth.session_service import AuthSessionService
from app.modules.parents.models import ParentAccount
from app.modules.teachers.models import TeacherAccount

router = APIRouter(prefix="/memberships", tags=["Auth Memberships"])
CurrentGlobalAccount: TypeAlias = Annotated[
    ParentAccount | TeacherAccount,
    Depends(get_current_actor),
]


@router.post("/select", response_model=LoginResponse)
async def select_membership(
    payload: MembershipSelectionRequest,
    db: DbSession,
    current_account: CurrentGlobalAccount,
    request: Request,
    response: Response,
) -> LoginResponse:
    """Issue a tenant membership session without asking for the password again."""

    if not isinstance(current_account, (ParentAccount, TeacherAccount)):
        raise ForbiddenException(
            "A global parent or teacher account session is required."
        )

    actor = await AuthService.select_membership(
        db,
        account=current_account,
        membership_id=payload.membership_id,
    )
    token_pair = await AuthSessionService.create_login_session(
        db,
        actor=actor,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
        remember_me=payload.remember_me,
    )
    _set_refresh_token_cookie(
        response,
        refresh_token=token_pair.refresh_token,
        expires_at=token_pair.refresh_token_expires_at,
    )
    return LoginResponse(
        access_token=token_pair.access_token,
        email=actor.email,
        actor_type=actor.actor_type,
        role=actor.role,
        account_type=actor.account_type,
        password_reset_required=actor.password_reset_required,
        user=actor.user,
    )
