# ====================================== #
#          cbt/auth/router.py            #
# ====================================== #

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Request,
)

from app.core.dependencies.db import DbSession
from app.core.exceptions import UnauthorizedException
from app.core.rate_limits.auth_rate_limits import AuthRateLimitService
from app.modules.cbt.auth.schemas import (
    AuthenticatedCBTServer,
    CBTStaffAuthResponse,
    CBTStaffLoginRequest,
)
from app.modules.cbt.auth.service import CBTStaffAuthService
from app.modules.cbt.dependencies import CurrentCBTServer


router = APIRouter(
    tags=["CBT Authentication"],
)


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None

    return request.client.host if request.client else None


@router.get(
    "/server/me",
    response_model=AuthenticatedCBTServer,
)
async def get_current_server(
    current_server: CurrentCBTServer,
) -> AuthenticatedCBTServer:
    return current_server


@router.post(
    "/auth/staff/login",
    response_model=CBTStaffAuthResponse,
)
async def authenticate_staff(
    payload: CBTStaffLoginRequest,
    db: DbSession,
    current_server: CurrentCBTServer,
    request: Request,
    background_tasks: BackgroundTasks,
) -> CBTStaffAuthResponse:

    client_ip = _client_ip(request)

    await AuthRateLimitService.check_login_allowed(
        identifier=str(payload.email),
        ip_address=client_ip,
    )

    try:
        result = await CBTStaffAuthService.authenticate_staff(
            db,
            payload=payload,
            current_server=current_server,
            client_ip=client_ip,
            background_tasks=background_tasks,
        )

    except UnauthorizedException:
        await AuthRateLimitService.record_failed_login(
            identifier=str(payload.email),
            ip_address=client_ip,
        )
        raise

    await AuthRateLimitService.clear_login_failures(
        identifier=str(payload.email),
        ip_address=client_ip,
    )

    return result
