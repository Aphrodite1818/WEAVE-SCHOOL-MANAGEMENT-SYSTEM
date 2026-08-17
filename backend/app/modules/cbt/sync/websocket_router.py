"""Authenticated machine WebSocket used for live CBT synchronization."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.core.exceptions import AppException, ForbiddenException
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.auth.service import CBTMachineAuthService
from app.modules.cbt.sync.manager import CBTMachineConnection, cbt_connection_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/sync", tags=["CBT Sync"])
AUTHENTICATION_CLOSE_CODE = 4401
FORBIDDEN_CLOSE_CODE = 4403


def _extract_bearer_credential(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization")
    if not authorization:
        return None
    scheme, separator, credential = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not credential.strip():
        return None
    return credential.strip()


async def _authenticate_server(credential: str) -> AuthenticatedCBTServer:
    async with AsyncSessionLocal() as db:
        return await CBTMachineAuthService.authenticate_server(
            db,
            server_credential=credential,
        )


async def _send(connection: CBTMachineConnection, message: dict) -> None:
    async with connection.send_lock:
        await asyncio.wait_for(connection.websocket.send_json(message), timeout=8.0)


@router.websocket("/stream")
async def cbt_sync_stream(websocket: WebSocket) -> None:
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
            current_server = await _authenticate_server(credential)
        except ForbiddenException:
            await websocket.close(
                code=FORBIDDEN_CLOSE_CODE,
                reason="CBT server is not permitted to synchronize.",
            )
            return
        except AppException:
            await websocket.close(
                code=AUTHENTICATION_CLOSE_CODE,
                reason="CBT server authentication failed.",
            )
            return

        await websocket.accept()
        connection = await cbt_connection_manager.register(
            server_id=current_server.server_id,
            credential_id=current_server.credential_id,
            tenant_id=current_server.tenant_id,
            websocket=websocket,
        )
        await _send(
            connection,
            {
                "type": "connection.ready",
                "server_id": str(current_server.server_id),
                "reconciliation_required": True,
            },
        )
        await _send(
            connection,
            {
                "type": "cbt.sync.reconcile",
                "reason": "connection_established",
            },
        )

        while True:
            message = await websocket.receive_json()
            if not await cbt_connection_manager.ensure_authorized(connection):
                return
            if not isinstance(message, dict):
                await _send(
                    connection,
                    {
                        "type": "error",
                        "code": "invalid_control_frame",
                        "message": "Control frames must be JSON objects.",
                    },
                )
                continue
            if message.get("type") == "ping":
                await _send(connection, {"type": "pong"})
                continue
            await _send(
                connection,
                {
                    "type": "error",
                    "code": "unsupported_control_frame",
                    "message": "Unsupported CBT synchronization control frame.",
                },
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Unexpected CBT synchronization WebSocket failure.")
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
