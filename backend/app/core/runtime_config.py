"""Public runtime configuration exposed to the frontend."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config.settings import EnvironmentType, settings

router = APIRouter(prefix="/runtime-config", tags=["Runtime Config"])


class RuntimeFeatureFlags(BaseModel):
    attendance: bool
    messaging: bool
    announcements: bool = True
    inbox: bool = True
    simulations: bool = False


class RuntimeConfigResponse(BaseModel):
    environment: str
    production_like: bool
    features: RuntimeFeatureFlags


@router.get("", response_model=RuntimeConfigResponse)
async def get_runtime_config() -> RuntimeConfigResponse:
    production_like = settings.is_production_like
    show_unreleased_features = settings.ENV != EnvironmentType.PRODUCTION
    return RuntimeConfigResponse(
        environment=settings.ENV.value,
        production_like=production_like,
        features=RuntimeFeatureFlags(
            attendance=show_unreleased_features,
            messaging=show_unreleased_features,
            simulations=settings.ENV == EnvironmentType.STAGING,
        ),
    )
