from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies.db import DbSession
from app.modules.cbt.dependencies import CurrentCBTServer
from app.modules.cbt.sync.schemas import CBTSyncDeltaResponse
from app.modules.cbt.sync.service import CBTSyncCursorExpired, CBTSyncService

router = APIRouter(prefix="/sync", tags=["CBT Sync"])


@router.get(
    "/changes",
    response_model=CBTSyncDeltaResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch CBT synchronization changes",
    description=(
        "Return ordered CBT-visible changes that occurred after the local CBT "
        "server's last successfully applied cursor."
    ),
)
async def get_sync_changes(
    db: DbSession,
    current_server: CurrentCBTServer,
    response: Response,
    after: int = Query(..., ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
) -> CBTSyncDeltaResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await CBTSyncService.get_changes_after(
            db,
            tenant_id=current_server.tenant_id,
            after_cursor=after,
            limit=limit,
        )
    except CBTSyncCursorExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CBT sync cursor expired; full bootstrap required.",
        ) from exc
