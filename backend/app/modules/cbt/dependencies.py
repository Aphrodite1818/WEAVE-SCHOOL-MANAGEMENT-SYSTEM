# ====================================== #
#         cbt/dependencies.py            #
# ====================================== #


"""This file defines a global dependency that routes can use to  verify and authenticate a request from a server"""

from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies.db import DbSession
from app.core.exceptions import UnauthorizedException
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.auth.service import CBTMachineAuthService

cbt_server_bearer = HTTPBearer(
    scheme_name="CBT Server Credenial",
    description=("Machine credential issued to a paired Weave CBT server"),
    auto_error=False,
)


async def get_current_cbt_server(
    db: DbSession,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Security(cbt_server_bearer)],
) -> AuthenticatedCBTServer:
    """
    Authenticate the CBT server making the current request
    """

    if authorization is None:
        raise UnauthorizedException(detail="CBT server authentication is required")

    return await CBTMachineAuthService.authenticate_server(
        db,
        server_credential=authorization.credentials,
    )


CurrentCBTServer = Annotated[AuthenticatedCBTServer, Security(get_current_cbt_server)]
