# ====================================== #
#             auth/router.py             #
# ====================================== #

"""Auth routes for login, refresh-token rotation, logout, OTP, and invites."""

from __future__ import annotations
from typing import Annotated

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response, status
from app.core.dependencies.route_guards import get_current_actor
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository

from app.config.settings import settings
from app.core.dependencies.db import DbSession
from app.core.exceptions import UnauthorizedException
from app.modules.auth.schemas import (
    LoginRequest,
    LoginSessionUser,
    RequestOTP,
    TenantActivationRequest,
    Token,
    UpdatePassword,
    UserInviteAcceptanceRequest,
    VerifyOTP,
    SessionBootstrapResponse
)
from app.modules.auth.service import (
    AuthService,
    AuthSessionService,
    OTPService,
    TenantActivationService,
    UserInviteService,
)


router = APIRouter()

REFRESH_TOKEN_COOKIE_NAME = "learnly_refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"


def _refresh_cookie_secure() -> bool:
    """Return whether refresh cookies should use the Secure flag."""

    return not settings.is_development


def _refresh_cookie_samesite() -> str:
    """Return the correct SameSite mode for the current environment."""

    return "lax" if settings.is_development else "none"


def _refresh_cookie_max_age(expires_at: datetime) -> int:
    """Return the remaining refresh-cookie lifetime in seconds."""

    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return max(int((expires_at - now).total_seconds()), 0)


def _set_refresh_token_cookie(
    response: Response,
    *,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    """Attach the raw refresh token as an HttpOnly cookie."""

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=_refresh_cookie_max_age(expires_at),
        path=REFRESH_COOKIE_PATH,
        secure=_refresh_cookie_secure(),
        httponly=True,
        samesite=_refresh_cookie_samesite(),
    )


def _delete_refresh_token_cookie(response: Response) -> None:
    """Clear the refresh-token cookie."""

    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=_refresh_cookie_secure(),
        httponly=True,
        samesite=_refresh_cookie_samesite(),
    )






CurrentActorDependency = Annotated[
    SuperAdmin | TenantAdmin | Teacher | Parent | Student,
    Depends(get_current_actor),
]


def _client_ip(request: Request) -> str | None:
    """Return the best client IP available behind a proxy/load balancer."""

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None

    return request.client.host if request.client else None


def _actor_type_and_role(
    actor: SuperAdmin | TenantAdmin | Teacher | Parent | Student,
) -> tuple[str, str]:
    """Return normalized actor_type and frontend role."""

    if isinstance(actor, SuperAdmin):
        return "superadmin", "superadmin"

    if isinstance(actor, TenantAdmin):
        return "tenant_admin", "admin"

    if isinstance(actor, Teacher):
        return "teacher", "teacher"

    if isinstance(actor, Parent):
        return "parent", "parent"

    if isinstance(actor, Student):
        return "student", "student"

    raise UnauthorizedException("Invalid session")


async def _build_session_bootstrap_response(
    db: DbSession,
    actor: SuperAdmin | TenantAdmin | Teacher | Parent | Student,
) -> SessionBootstrapResponse:
    """Build a safe current-session response for frontend bootstrapping."""

    actor_type, role = _actor_type_and_role(actor)

    tenant_id = getattr(actor, "tenant_id", None)
    school_name = None

    if tenant_id is not None:
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        school_name = tenant.school_name if tenant else None

    if isinstance(actor, Student):
        email = actor.admission_number
        admission_number = actor.admission_number
    else:
        email = getattr(actor, "email", None)
        admission_number = None

    user = LoginSessionUser(
        id=str(actor.id),
        tenant_id=str(tenant_id) if tenant_id else None,
        school_name=school_name,
        email=email,
        admission_number=admission_number,
        first_name=getattr(actor, "first_name", None),
        last_name=getattr(actor, "last_name", None),
        actor_type=actor_type,
        account_type=actor_type,
        role=role,
        password_reset_required=getattr(actor, "password_reset_required", None),
        profile_status=(
            getattr(getattr(actor, "profile_status", None), "value", None)
            or str(getattr(actor, "profile_status", ""))
            if getattr(actor, "profile_status", None) is not None
            else None
        ),
    )

    return SessionBootstrapResponse(
        authenticated=True,
        actor_type=actor_type,
        account_type=actor_type,
        role=role,
        tenant_id=str(tenant_id) if tenant_id else None,
        email=email,
        password_reset_required=getattr(actor, "password_reset_required", None),
        user=user,
    )


class LoginResponse(Token):
    """Login response returned to the frontend."""

    detail: str | None = None
    resend_otp_available: bool = False
    email: str | None = None
    actor_type: str | None = None
    role: str | None = None
    account_type: str | None = None
    password_reset_required: bool | None = None
    user: LoginSessionUser | None = None


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
) -> LoginResponse:
    """Authenticate an actor and create a persistent refresh-token session."""

    actor = await AuthService.authenticate_actor(
        db,
        payload,
        background_tasks=background_tasks,
    )

    token_pair = await AuthSessionService.create_login_session(
        db,
        actor=actor,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
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


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    db: DbSession,
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
) -> Token:
    """Rotate the refresh token and issue a new access token."""

    if refresh_token is None:
        raise UnauthorizedException("Invalid session")

    token_pair = await AuthSessionService.rotate_refresh_token(
        db,
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    _set_refresh_token_cookie(
        response,
        refresh_token=token_pair.refresh_token,
        expires_at=token_pair.refresh_token_expires_at,
    )

    return Token(access_token=token_pair.access_token)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    db: DbSession,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
) -> dict[str, str]:
    """Revoke the current refresh-token session and clear the cookie."""

    if refresh_token is not None:
        await AuthSessionService.logout_by_refresh_token(
            db,
            refresh_token=refresh_token,
        )

    _delete_refresh_token_cookie(response)
    return {"detail": "Logged out successfully."}






@router.get("/me/session", response_model=SessionBootstrapResponse)
async def get_current_session(
    db: DbSession,
    current_actor: CurrentActorDependency,
) -> SessionBootstrapResponse:
    """Return the current authenticated session/user payload."""

    return await _build_session_bootstrap_response(db, current_actor)






@router.post("/request-otp")
async def request_otp(
    payload: RequestOTP,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Request an OTP for verification or password reset."""

    await OTPService.generate_otp(
        db,
        payload,
        background_tasks=background_tasks,
    )

    return {"detail": f"OTP successfully sent to {payload.email}"}


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOTP, db: DbSession) -> dict[str, str]:
    """Verify an OTP."""

    return await OTPService.verify_otp(db, payload)


@router.post("/reset-password")
async def reset_password(payload: UpdatePassword, db: DbSession) -> dict[str, str]:
    """Reset an account password."""

    await AuthService.reset_password(db, payload)
    return {"detail": "Password has been successfully reset. You may now log in."}


@router.post("/activate-tenant")
async def activate_tenant(
    payload: TenantActivationRequest,
    db: DbSession,
) -> dict[str, str]:
    """Activate a tenant admin account."""

    return await TenantActivationService.activate_tenant(db, payload)


@router.get("/invite-status")
async def get_invite_status(token: str, db: DbSession) -> dict[str, str | None]:
    """Return invite status."""

    return await UserInviteService.get_invite_status(db, token)


@router.post("/accept-invite")
async def accept_invite(
    payload: UserInviteAcceptanceRequest,
    db: DbSession,
) -> dict[str, str]:
    """Accept a tenant user or superadmin invite without auto-login."""

    result = await UserInviteService.accept_invite(db, payload)
    return {"detail": result.get("detail", "Account setup completed successfully.")}
