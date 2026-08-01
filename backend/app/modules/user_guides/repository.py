"""Persistence helpers for role-aware product guides."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user_guides.models import UserGuideState


class UserGuideRepository:
    @staticmethod
    async def get_state(
        db: AsyncSession,
        *,
        actor_type: str,
        actor_id: uuid.UUID,
        scope_key: str,
        guide_key: str,
        for_update: bool = False,
    ) -> UserGuideState | None:
        statement = select(UserGuideState).where(
            UserGuideState.actor_type == actor_type,
            UserGuideState.actor_id == actor_id,
            UserGuideState.scope_key == scope_key,
            UserGuideState.guide_key == guide_key,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def save(db: AsyncSession, state: UserGuideState) -> UserGuideState:
        db.add(state)
        await db.flush()
        await db.refresh(state)
        return state
