# ====================================== #
#      cbt/academics/router.py           #
# ====================================== #

"""Routes used by paired CBT servers to synchronize academic state."""

from fastapi import APIRouter, Response, status

from app.core.dependencies.db import DbSession
from app.modules.cbt.academics.schemas import CBTAcademicBootstrapResponse
from app.modules.cbt.academics.service import CBTAcademicSyncService
from app.modules.cbt.dependencies import CurrentCBTServer


router = APIRouter(
    prefix="/academics",
    tags=["CBT Academics"],
)


@router.get(
    "/bootstrap",
    response_model=CBTAcademicBootstrapResponse,
    status_code=status.HTTP_200_OK,
    summary="Bootstrap CBT academic state",
    description=(
        "Return the complete current academic snapshot required by an "
        "authenticated paired CBT server."
    ),
)
async def bootstrap_academics(
    db: DbSession,
    current_server: CurrentCBTServer,
    response: Response,
) -> CBTAcademicBootstrapResponse:
    """Return the initial Cloud -> CBT academic synchronization snapshot."""

    # Academic bootstrap data contains tenant-specific student/staff state.
    # Never allow an intermediary/shared cache to retain the response.
    response.headers["Cache-Control"] = "no-store"

    return await CBTAcademicSyncService.build_bootstrap(
        db,
        current_server=current_server,
    )
