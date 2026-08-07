"""Actor-scoped product-guide lifecycle service."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user_guides.models import UserGuideState
from app.modules.user_guides.repository import UserGuideRepository
from app.modules.user_guides.schemas import UserGuideStateResponse, UserGuideStateUpdate

_ACTOR_TYPE_BY_CLASS_NAME = {
    "TenantAdmin": "tenant_admin",
    "Teacher": "teacher",
    "TeacherAccount": "teacher_account",
    "Parent": "parent",
    "ParentAccount": "parent_account",
    "Student": "student",
    "SuperAdmin": "superadmin",
}
_GUIDE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,99}$")
_TERMINAL_GUIDE_STATUSES = frozenset({"completed", "dismissed"})


@dataclass(slots=True, frozen=True)
class GuideActorContext:
    actor_type: str
    actor_id: uuid.UUID
    tenant_id: uuid.UUID | None
    scope_key: str


class UserGuideService:
    @staticmethod
    def actor_context(actor: Any) -> GuideActorContext:
        actor_id = getattr(actor, "id", None)
        if not isinstance(actor_id, uuid.UUID):
            raise ValueError("The authenticated actor does not expose a valid identifier.")

        actor_type = _ACTOR_TYPE_BY_CLASS_NAME.get(actor.__class__.__name__)
        if actor_type is None:
            raise ValueError("This actor type does not support product guides.")

        tenant_id = getattr(actor, "tenant_id", None)
        if tenant_id is not None and not isinstance(tenant_id, uuid.UUID):
            tenant_id = uuid.UUID(str(tenant_id))
        scope_key = str(tenant_id) if tenant_id is not None else "global"
        return GuideActorContext(
            actor_type=actor_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            scope_key=scope_key,
        )

    @staticmethod
    def validate_guide_key(guide_key: str) -> str:
        normalized = guide_key.strip().lower()
        if not _GUIDE_KEY_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid guide key.")
        return normalized

    @staticmethod
    def _response(
        *,
        context: GuideActorContext,
        guide_key: str,
        state: UserGuideState | None,
    ) -> UserGuideStateResponse:
        if state is not None:
            return UserGuideStateResponse.model_validate(state)
        return UserGuideStateResponse(
            guide_key=guide_key,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            tenant_id=context.tenant_id,
            status="not_started",
            skipped_steps=[],
        )

    @staticmethod
    def _preserve_terminal_state(
        current_status: str,
        requested_status: str | None,
    ) -> bool:
        """Prevent stale clients from reopening a finished guide.

        Completion is final. Dismissal may only be upgraded to completion. This makes
        duplicate dashboard/guide hooks and delayed requests idempotent instead of
        allowing an old ``in_progress`` request to overwrite a terminal state.
        """

        if current_status == "completed":
            return requested_status != "completed"
        if current_status == "dismissed":
            return requested_status not in _TERMINAL_GUIDE_STATUSES
        return False

    @staticmethod
    async def get_state(
        db: AsyncSession,
        *,
        actor: Any,
        guide_key: str,
    ) -> UserGuideStateResponse:
        context = UserGuideService.actor_context(actor)
        normalized_key = UserGuideService.validate_guide_key(guide_key)
        state = await UserGuideRepository.get_state(
            db,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            scope_key=context.scope_key,
            guide_key=normalized_key,
        )
        return UserGuideService._response(
            context=context,
            guide_key=normalized_key,
            state=state,
        )

    @staticmethod
    async def update_state(
        db: AsyncSession,
        *,
        actor: Any,
        guide_key: str,
        payload: UserGuideStateUpdate,
    ) -> UserGuideStateResponse:
        context = UserGuideService.actor_context(actor)
        normalized_key = UserGuideService.validate_guide_key(guide_key)
        now = datetime.now(timezone.utc)
        state = await UserGuideRepository.get_state(
            db,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            scope_key=context.scope_key,
            guide_key=normalized_key,
            for_update=True,
        )
        if state is None:
            state = UserGuideState(
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                tenant_id=context.tenant_id,
                scope_key=context.scope_key,
                guide_key=normalized_key,
            )

        changes = payload.model_dump(exclude_unset=True)
        requested_status = changes.get("status")
        if UserGuideService._preserve_terminal_state(
            state.status,
            requested_status,
        ):
            state.last_seen_at = now
            saved = await UserGuideRepository.save(db, state)
            await db.commit()
            return UserGuideService._response(
                context=context,
                guide_key=normalized_key,
                state=saved,
            )

        if "current_step" in changes:
            state.current_step = changes["current_step"] or None
        if "skipped_steps" in changes:
            state.skipped_steps = list(
                dict.fromkeys(
                    step.strip()
                    for step in (changes["skipped_steps"] or [])
                    if step and step.strip()
                )
            )
        if "remind_after" in changes:
            state.remind_after = changes["remind_after"]
        if "status" in changes and changes["status"] is not None:
            state.status = changes["status"]
            if state.status == "completed":
                state.completed_at = now
                state.dismissed_at = None
                state.remind_after = None
            elif state.status == "dismissed":
                state.dismissed_at = now
                state.completed_at = None
                state.remind_after = None
            else:
                state.dismissed_at = None
                state.completed_at = None
        state.last_seen_at = now

        saved = await UserGuideRepository.save(db, state)
        await db.commit()
        return UserGuideService._response(
            context=context,
            guide_key=normalized_key,
            state=saved,
        )
