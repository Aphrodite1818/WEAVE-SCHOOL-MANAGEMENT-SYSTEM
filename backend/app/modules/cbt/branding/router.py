"""Routes used by paired CBT servers to fetch effective tenant branding."""

from fastapi import APIRouter, Response, status

from app.core.dependencies.db import DbSession
from app.modules.cbt.branding.schemas import CBTBrandingProjectionResponse
from app.modules.cbt.branding.service import CBTBrandingProjectionService
from app.modules.cbt.dependencies import CurrentCBTServer


router = APIRouter(
    prefix="/branding",
    tags=["CBT Branding"],
)


@router.get(
    "",
    response_model=CBTBrandingProjectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get CBT tenant branding",
)
async def get_cbt_branding(
    db: DbSession,
    current_server: CurrentCBTServer,
    response: Response,
) -> CBTBrandingProjectionResponse:
    """Return effective Cloud -> CBT tenant branding for the authenticated server."""

    response.headers["Cache-Control"] = "no-store"
    return await CBTBrandingProjectionService.build_projection(
        db,
        current_server=current_server,
    )
