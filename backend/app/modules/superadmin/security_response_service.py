from __future__ import annotations

import hashlib
import hmac
import ipaddress
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.manager import CacheManager
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException, PlatformMaintenanceException
from app.modules.auth.models import AuthRefreshToken, AuthSession, AuthSessionActorType
from app.modules.superadmin.models import SecurityIPBlock, SuperAdmin
from app.modules.superadmin.schemas import (
    SecurityIPBlockCreate,
    SecurityIPBlockUnblock,
    SecurityRevokeActorSessionsRequest,
    SecurityRevokeIPSessionsRequest,
)
from app.modules.superadmin.security_alert_service import SecurityAlertService
from fastapi import BackgroundTasks


SECURITY_IP_BLOCK_CACHE_PREFIX = "security:ip-block"
SECURITY_IP_BLOCK_CACHE_TTL_SECONDS = 30


class SecurityResponseService:
    """Superadmin damage-control operations for suspicious auth activity."""

    @staticmethod
    def normalize_ip_address(ip_address: str | None) -> str | None:
        """Return a canonical IP string, or None when the input is invalid."""

        if not ip_address:
            return None

        candidate = ip_address.split(",")[0].strip()
        if not candidate:
            return None

        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return None

    @staticmethod
    def hash_ip_address(ip_address: str) -> str:
        """Hash an IP address for database storage."""

        digest = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            ip_address.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"ip_sha256${digest}"

    @staticmethod
    def mask_ip_address(ip_address: str) -> str:
        """Return a safe IP label for dashboard display."""

        try:
            parsed_ip = ipaddress.ip_address(ip_address)
        except ValueError:
            return "invalid-ip"

        if parsed_ip.version == 4:
            parts = ip_address.split(".")
            return f"{parts[0]}.{parts[1]}.xxx.xxx"

        groups = parsed_ip.exploded.split(":")
        return ":".join(groups[:3] + ["xxxx", "xxxx", "xxxx", "xxxx", "xxxx"])

    @classmethod
    def _cache_key(cls, ip_address: str) -> str:
        return f"{SECURITY_IP_BLOCK_CACHE_PREFIX}:{cls.hash_ip_address(ip_address)}"

    @classmethod
    async def _active_block_for_ip(cls, db: AsyncSession, ip_address: str) -> SecurityIPBlock | None:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(SecurityIPBlock)
            .where(
                SecurityIPBlock.ip_address_hash == cls.hash_ip_address(ip_address),
                SecurityIPBlock.is_active.is_(True),
                SecurityIPBlock.unblocked_at.is_(None),
                (SecurityIPBlock.expires_at.is_(None)) | (SecurityIPBlock.expires_at > now),
            )
            .order_by(SecurityIPBlock.blocked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def is_ip_blocked(cls, db: AsyncSession, ip_address: str | None) -> dict[str, Any]:
        """Return active IP block state for middleware checks."""

        normalized_ip = cls.normalize_ip_address(ip_address)
        if not normalized_ip:
            return {"blocked": False}

        cache_key = cls._cache_key(normalized_ip)
        cached_state = await CacheManager.get_json(cache_key)
        if isinstance(cached_state, dict):
            return cached_state

        block = await cls._active_block_for_ip(db, normalized_ip)
        state = {
            "blocked": block is not None,
            "ip_label": block.ip_address_label if block else cls.mask_ip_address(normalized_ip),
            "reason": block.reason if block else None,
            "expires_at": block.expires_at.isoformat() if block and block.expires_at else None,
        }
        await CacheManager.set_json(cache_key, state, SECURITY_IP_BLOCK_CACHE_TTL_SECONDS)
        return state

    @classmethod
    async def enforce_actor_ip_allowed(
        cls,
        db: AsyncSession,
        *,
        ip_address: str | None,
        actor_type: str | AuthSessionActorType | None,
    ) -> None:
        """Block non-superadmin login when the source IP is manually blocked."""

        state = await cls.is_ip_blocked(db, ip_address)
        if not state.get("blocked"):
            return

        actor_type_value = getattr(actor_type, "value", actor_type)
        if actor_type_value == AuthSessionActorType.SUPERADMIN.value:
            return

        raise PlatformMaintenanceException(
            detail="Access from this network has been temporarily blocked for security reasons.",
            reason=str(state.get("reason") or "Manual IP block is active."),
        )

    @classmethod
    async def list_ip_blocks(
        cls,
        db: AsyncSession,
        *,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> list[SecurityIPBlock]:
        """List manual IP blocks."""

        statement = select(SecurityIPBlock).order_by(SecurityIPBlock.blocked_at.desc()).limit(limit)
        if not include_inactive:
            statement = statement.where(SecurityIPBlock.is_active.is_(True))

        result = await db.execute(statement)
        return list(result.scalars().all())

    @classmethod
    async def block_ip(
        cls,
        db: AsyncSession,
        *,
        background_tasks: BackgroundTasks,
        current_superadmin: SuperAdmin,
        payload: SecurityIPBlockCreate,
    ) -> SecurityIPBlock:
        """Create a manual IP block rule."""

        normalized_ip = cls.normalize_ip_address(payload.ip_address)
        if not normalized_ip:
            raise BadRequestException("Enter a valid IPv4 or IPv6 address.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=payload.duration_hours) if payload.duration_hours else None
        block = SecurityIPBlock(
            ip_address_hash=cls.hash_ip_address(normalized_ip),
            ip_address_label=cls.mask_ip_address(normalized_ip),
            reason=payload.reason,
            blocked_by_superadmin_id=current_superadmin.id,
            blocked_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(block)
        await db.commit()
        await db.refresh(block)
        await CacheManager.delete(cls._cache_key(normalized_ip))
        SecurityAlertService.notify_ip_block_created(
            background_tasks=background_tasks,
            ip_label=block.ip_address_label,
            superadmin_id=current_superadmin.id,
            reason=block.reason,
            expires_at=block.expires_at.isoformat() if block.expires_at else None,
        )
        return block

    @classmethod
    async def unblock_ip(
        cls,
        db: AsyncSession,
        *,
        block_id: uuid.UUID,
        current_superadmin: SuperAdmin,
        payload: SecurityIPBlockUnblock,
    ) -> SecurityIPBlock:
        """Disable a manual IP block rule."""

        result = await db.execute(select(SecurityIPBlock).where(SecurityIPBlock.id == block_id))
        block = result.scalar_one_or_none()
        if block is None:
            raise NotFoundException("IP block not found")

        now = datetime.now(timezone.utc)
        block.is_active = False
        block.unblocked_by_superadmin_id = current_superadmin.id
        block.unblocked_at = now
        block.unblock_reason = payload.reason
        db.add(block)
        await db.commit()
        await db.refresh(block)
        await CacheManager.delete(f"{SECURITY_IP_BLOCK_CACHE_PREFIX}:{block.ip_address_hash}")
        return block

    @classmethod
    async def revoke_sessions_for_ip(
        cls,
        db: AsyncSession,
        *,
        current_superadmin: SuperAdmin,
        payload: SecurityRevokeIPSessionsRequest,
    ) -> int:
        """Revoke active sessions created from a specific IP address."""

        normalized_ip = cls.normalize_ip_address(payload.ip_address)
        if not normalized_ip:
            raise BadRequestException("Enter a valid IPv4 or IPv6 address.")

        now = datetime.now(timezone.utc)
        result = await db.execute(
            update(AuthSession)
            .where(
                AuthSession.ip_address == normalized_ip,
                AuthSession.actor_type != AuthSessionActorType.SUPERADMIN,
                AuthSession.revoked_at.is_(None),
                AuthSession.compromised_at.is_(None),
            )
            .values(
                revoked_at=now,
                revoked_reason=payload.reason,
            )
        )
        affected_count = result.rowcount or 0

        if affected_count:
            session_ids = await db.execute(
                select(AuthSession.id).where(
                    AuthSession.ip_address == normalized_ip,
                    AuthSession.revoked_at == now,
                )
            )
            ids = [row[0] for row in session_ids.all()]
            if ids:
                await db.execute(
                    update(AuthRefreshToken)
                    .where(
                        AuthRefreshToken.session_id.in_(ids),
                        AuthRefreshToken.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=now,
                        revoked_reason=payload.reason,
                    )
                )

        await db.commit()
        return affected_count

    @classmethod
    async def revoke_sessions_for_actor(
        cls,
        db: AsyncSession,
        *,
        current_superadmin: SuperAdmin,
        payload: SecurityRevokeActorSessionsRequest,
    ) -> int:
        """Revoke active sessions for one actor."""

        try:
            actor_type = AuthSessionActorType(payload.actor_type)
        except ValueError as exc:
            raise BadRequestException("Unsupported actor type.") from exc

        if actor_type == AuthSessionActorType.SUPERADMIN and payload.actor_id == current_superadmin.id:
            raise ForbiddenException("You cannot revoke your own superadmin sessions from this action.")

        now = datetime.now(timezone.utc)
        session_ids_result = await db.execute(
            select(AuthSession.id).where(
                AuthSession.actor_type == actor_type,
                AuthSession.actor_id == payload.actor_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.compromised_at.is_(None),
            )
        )
        session_ids = [row[0] for row in session_ids_result.all()]
        if not session_ids:
            return 0

        await db.execute(
            update(AuthSession)
            .where(AuthSession.id.in_(session_ids))
            .values(
                revoked_at=now,
                revoked_reason=payload.reason,
            )
        )
        await db.execute(
            update(AuthRefreshToken)
            .where(
                AuthRefreshToken.session_id.in_(session_ids),
                AuthRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=now,
                revoked_reason=payload.reason,
            )
        )
        await db.commit()
        return len(session_ids)
