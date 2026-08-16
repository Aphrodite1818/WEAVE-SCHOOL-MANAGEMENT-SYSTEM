# ==============================================#
# backend.app.modules.cbt.sync.websocket_router
# ==============================================#

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.core.exceptions import AppException
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.auth.service import CBTMachineAuthService
from app.modules.cbt.sync.manager import (
    CBTMachineConnection,
    cbt_connection_manager,
)


logger = get_logger(__name__)

router = APIRouter(
    prefix="/sync",
    tags=["CBT Sync"],
)

AUTHENTICATION_CLOSE_CODE = 4401
FORBIDDEN_CLOSE_CODE = 4403


def _extract_bearer_credential(
    websocket: WebSocket,
) -> str | None:
    """
    Extract the CBT machine credential from the WebSocket
    Authorization header.
    """

    authorization = websocket.headers.get("authorization")

    if not authorization:
        return None

    scheme, separator, credential = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not credential.strip()
    ):
        return None

    return credential.strip()


async def _authenticate_server(
    credential: str,
) -> AuthenticatedCBTServer:
    """
    Authenticate the machine using a short-lived database session.

    The database session is deliberately not kept for the lifetime
    of the WebSocket connection.
    """

    async with AsyncSessionLocal() as db:
        return await CBTMachineAuthService.authenticate_server(
            db,
            server_credential=credential,
        )


async def _send(
    connection: CBTMachineConnection,
    message: dict,
) -> None:
    """
    Send a control frame while respecting the connection's
    per-socket send lock.
    """

    async with connection.send_lock:
        await connection.websocket.send_json(message)


@router.websocket("/stream")
async def cbt_sync_stream(
    websocket: WebSocket,
) -> None:
    """
    Maintain one authenticated Cloud -> CBT synchronization stream.
    """

    connection: CBTMachineConnection | None = None

    credential = _extract_bearer_credential(websocket)

    if credential is None:
        await websocket.close(
            code=AUTHENTICATION_CLOSE_CODE,
            reason="CBT server authentication is required.",
        )
        return

    try:
        try:
            current_server = await _authenticate_server(
                credential
            )
        except AppException:
            await websocket.close(
                code=AUTHENTICATION_CLOSE_CODE,
                reason="CBT server authentication failed.",
            )
            return

        await websocket.accept()

        connection = await cbt_connection_manager.register(
            server_id=current_server.server_id,
            tenant_id=current_server.tenant_id,
            websocket=websocket,
        )

        await _send(
            connection,
            {
                "type": "connection.ready",
                "server_id": str(current_server.server_id),
            },
        )

        while True:
            message = await websocket.receive_json()

            message_type = message.get("type")

            if message_type == "ping":
                await _send(
                    connection,
                    {
                        "type": "pong",
                    },
                )
                continue

            await _send(
                connection,
                {
                    "type": "error",
                    "code": "unsupported_control_frame",
                    "message": (
                        "Unsupported CBT synchronization "
                        "control frame."
                    ),
                },
            )

    except WebSocketDisconnect:
        pass

    except Exception:
        logger.exception(
            "Unexpected CBT synchronization WebSocket failure."
        )

        if connection is not None:
            try:
                await _send(
                    connection,
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": (
                            "The CBT synchronization connection "
                            "closed unexpectedly."
                        ),
                    },
                )
            except Exception:
                pass

        try:
            await websocket.close(code=1011)
        except Exception:
            pass

    finally:
        if connection is not None:
            await cbt_connection_manager.unregister(
                server_id=connection.server_id,
                websocket=websocket,
            )