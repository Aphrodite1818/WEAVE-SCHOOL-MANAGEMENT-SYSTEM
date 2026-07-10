from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.manager import CacheManager
from app.core.exceptions import BadRequestException, PlatformMaintenanceException
from app.modules.auth.models import AuthSessionActorType
from app.modules.superadmin.models import PlatformControl, SuperAdmin
from app.modules.superadmin.schemas import PlatformLockdownRequest, PlatformUnlockRequest
from app.modules.superadmin.schemas import PlatformLockdownRequest, PlatformUnlockRequest
from app.modules.superadmin.security_alert_service import SecurityAlertService
from fastapi import BackgroundTasks


PLATFORM_LOCKDOWN_CACHE_KEY = "platform:control:lockdown"
PLATFORM_LOCKDOWN_CACHE_TTL_SECONDS = 15
DEFAULT_MAINTENANCE_MESSAGE = "LearnlyAI is temporarily in maintenance mode. Please try again later."


class PlatformControlService:
    """Business logic for emergency platform lockdown mode."""

    @staticmethod
    def _control_to_state(control: PlatformControl | None) -> dict[str, Any]:
        if control is None:
            return {
                "id": None,
                "lockdown_enabled": False,
                "lockdown_reason": None,
                "lockdown_message": DEFAULT_MAINTENANCE_MESSAGE,
                "enabled_by_superadmin_id": None,
                "enabled_at": None,
                "disabled_by_superadmin_id": None,
                "disabled_at": None,
                "updated_at": None,
            }

        return {
            "id": str(control.id),
            "lockdown_enabled": bool(control.lockdown_enabled),
            "lockdown_reason": control.lockdown_reason,
            "lockdown_message": control.lockdown_message or DEFAULT_MAINTENANCE_MESSAGE,
            "enabled_by_superadmin_id": str(control.enabled_by_superadmin_id) if control.enabled_by_superadmin_id else None,
            "enabled_at": control.enabled_at.isoformat() if control.enabled_at else None,
            "disabled_by_superadmin_id": str(control.disabled_by_superadmin_id) if control.disabled_by_superadmin_id else None,
            "disabled_at": control.disabled_at.isoformat() if control.disabled_at else None,
            "updated_at": control.updated_at.isoformat() if control.updated_at else None,
        }

    @staticmethod
    async def _get_control(db: AsyncSession, *, lock: bool = False) -> PlatformControl | None:
        statement = select(PlatformControl).order_by(PlatformControl.created_at.asc()).limit(1)
        if lock:
            statement = statement.with_for_update()

        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @classmethod
    async def _get_or_create_control(cls, db: AsyncSession) -> PlatformControl:
        control = await cls._get_control(db, lock=True)
        if control is not None:
            return control

        control = PlatformControl(lockdown_message=DEFAULT_MAINTENANCE_MESSAGE)
        db.add(control)
        await db.flush()
        return control

    @classmethod
    async def get_state(cls, db: AsyncSession, *, use_cache: bool = True) -> dict[str, Any]:
        """Return the current platform-control state."""

        if use_cache:
            cached_state = await CacheManager.get_json(PLATFORM_LOCKDOWN_CACHE_KEY)
            if isinstance(cached_state, dict):
                return cached_state

        control = await cls._get_control(db)
        state = cls._control_to_state(control)
        await CacheManager.set_json(
            PLATFORM_LOCKDOWN_CACHE_KEY,
            state,
            PLATFORM_LOCKDOWN_CACHE_TTL_SECONDS,
        )
        return state

    @classmethod
    async def get_response(cls, db: AsyncSession) -> dict[str, Any]:
        """Return the current platform-control state for API responses."""

        return await cls.get_state(db, use_cache=False)

    @classmethod
    async def is_lockdown_active(cls, db: AsyncSession) -> bool:
        """Return whether emergency lockdown is active."""

        state = await cls.get_state(db)
        return bool(state.get("lockdown_enabled"))

    @classmethod
    async def enforce_actor_allowed(
        cls,
        db: AsyncSession,
        *,
        actor_type: str | AuthSessionActorType | None,
    ) -> None:
        """Block non-superadmin actors during platform lockdown."""

        state = await cls.get_state(db)
        if not state.get("lockdown_enabled"):
            return

        actor_type_value = getattr(actor_type, "value", actor_type)
        if actor_type_value == AuthSessionActorType.SUPERADMIN.value:
            return

        raise PlatformMaintenanceException(
            detail=str(state.get("lockdown_message") or DEFAULT_MAINTENANCE_MESSAGE),
            reason=str(state.get("lockdown_reason") or "Platform lockdown is active."),
        )

    @classmethod
    async def enable_lockdown(
        cls,
        db: AsyncSession,
        *,
        background_tasks: BackgroundTasks,
        current_superadmin: SuperAdmin,
        payload: PlatformLockdownRequest,
    ) -> PlatformControl:
        """Enable platform-wide maintenance lockdown."""

        if payload.confirmation != "LOCKDOWN":
            raise BadRequestException("Type LOCKDOWN to confirm platform lockdown.")

        now = datetime.now(timezone.utc)
        control = await cls._get_or_create_control(db)
        control.lockdown_enabled = True
        control.lockdown_reason = payload.reason
        control.lockdown_message = payload.message or DEFAULT_MAINTENANCE_MESSAGE
        control.enabled_by_superadmin_id = current_superadmin.id
        control.enabled_at = now
        control.disabled_by_superadmin_id = None
        control.disabled_at = None

        db.add(control)
        await db.commit()
        await db.refresh(control)
        await CacheManager.delete(PLATFORM_LOCKDOWN_CACHE_KEY)
        await CacheManager.delete(PLATFORM_LOCKDOWN_CACHE_KEY)
        SecurityAlertService.notify_platform_lockdown_change(
            background_tasks=background_tasks,
            enabled=True,
            superadmin_id=current_superadmin.id,
            reason=payload.reason,
        )
        return control

    @classmethod
    async def disable_lockdown(
        cls,
        db: AsyncSession,
        *,
        background_tasks: BackgroundTasks,
        current_superadmin: SuperAdmin,
        payload: PlatformUnlockRequest,
    ) -> PlatformControl:
        """Disable platform-wide maintenance lockdown."""

        if payload.confirmation != "UNLOCK":
            raise BadRequestException("Type UNLOCK to confirm platform unlock.")

        now = datetime.now(timezone.utc)
        control = await cls._get_or_create_control(db)
        control.lockdown_enabled = False
        control.disabled_by_superadmin_id = current_superadmin.id
        control.disabled_at = now

        db.add(control)
        await db.commit()
        await db.refresh(control)
        await CacheManager.delete(PLATFORM_LOCKDOWN_CACHE_KEY)
        await CacheManager.delete(PLATFORM_LOCKDOWN_CACHE_KEY)
        SecurityAlertService.notify_platform_lockdown_change(
            background_tasks=background_tasks,
            enabled=False,
            superadmin_id=current_superadmin.id,
            reason=control.lockdown_reason,
        )
        return control
