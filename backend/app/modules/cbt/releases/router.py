"""Public release metadata endpoint for WEAVE CBT installers and Manager updates."""

from fastapi import APIRouter, HTTPException, status

from app.modules.cbt.releases.schemas import CBTReleaseResponse
from app.modules.cbt.releases.service import (
    CBTReleaseService,
    CBTReleaseUnavailableError,
)

router = APIRouter(tags=["CBT Releases"])


@router.get("/releases/latest", response_model=CBTReleaseResponse)
async def get_latest_cbt_release() -> CBTReleaseResponse:
    """Return the installer release matching the active Weave environment."""

    try:
        return await CBTReleaseService.get_latest()
    except CBTReleaseUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
