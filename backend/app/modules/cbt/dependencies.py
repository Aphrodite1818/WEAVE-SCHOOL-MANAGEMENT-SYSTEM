# ====================================== #
#         cbt/dependencies.py            #
# ====================================== #

"""Authentication dependencies shared by CBT cloud-facing routes."""

from typing import Annotated

from fastapi import Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies.db import DbSession
from app.core.exceptions import UnauthorizedException
from app.modules.cbt.auth.schemas import AuthenticatedCBTActor, AuthenticatedCBTServer
from app.modules.cbt.auth.service import (
    CBTActorAuthorizationService,
    CBTMachineAuthService,
)

cbt_server_bearer = HTTPBearer(
    scheme_name="CBT Server Credential",
    description="Machine credential issued to a paired Weave CBT server",
    auto_error=False,
)


async def get_current_cbt_server(
    db: DbSession,
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(cbt_server_bearer),
    ],
) -> AuthenticatedCBTServer:
    """Authenticate the CBT server making the current request."""

    if authorization is None:
        raise UnauthorizedException(detail="CBT server authentication is required")

    return await CBTMachineAuthService.authenticate_server(
        db,
        server_credential=authorization.credentials,
    )


CurrentCBTServer = Annotated[AuthenticatedCBTServer, Security(get_current_cbt_server)]


async def get_current_cbt_actor(
    db: DbSession,
    current_server: CurrentCBTServer,
    actor_authorization: Annotated[
        str | None,
        Header(alias="X-CBT-Actor-Authorization"),
    ] = None,
) -> AuthenticatedCBTActor:
    """Authenticate the human actor responsible for a CBT cloud request."""

    if not actor_authorization:
        raise UnauthorizedException(detail="CBT actor authorization is required")

    return await CBTActorAuthorizationService.authenticate_actor(
        db,
        current_server=current_server,
        access_token=actor_authorization,
    )


CurrentCBTActor = Annotated[AuthenticatedCBTActor, Security(get_current_cbt_actor)]
