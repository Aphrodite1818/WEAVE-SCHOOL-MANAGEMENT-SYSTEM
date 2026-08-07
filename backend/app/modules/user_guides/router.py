"""Authenticated product-guide state endpoints."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Path

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import CurrentActor, get_current_actor
from app.core.exceptions import BadRequestException
from app.modules.user_guides.schemas import UserGuideStateResponse, UserGuideStateUpdate
from app.modules.user_guides.service import UserGuideService

router = APIRouter(prefix="/guides", tags=["User Guides"])
CurrentGuideActor: TypeAlias = Annotated[CurrentActor, Depends(get_current_actor)]
GuideKey = Annotated[str, Path(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]+$")]


@router.get("/{guide_key}", response_model=UserGuideStateResponse)
async def get_user_guide_state(
    guide_key: GuideKey,
    db: DbSession,
    current_actor: CurrentGuideActor,
) -> UserGuideStateResponse:
    try:
        return await UserGuideService.get_state(
            db,
            actor=current_actor,
            guide_key=guide_key,
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc


@router.patch("/{guide_key}", response_model=UserGuideStateResponse)
async def update_user_guide_state(
    guide_key: GuideKey,
    payload: UserGuideStateUpdate,
    db: DbSession,
    current_actor: CurrentGuideActor,
) -> UserGuideStateResponse:
    try:
        return await UserGuideService.update_state(
            db,
            actor=current_actor,
            guide_key=guide_key,
            payload=payload,
        )
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
