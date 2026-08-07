# ====================================== #
#        auth/repository.py              #
# ====================================== #

"""Data access layer for auth sessions and refresh tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    AuthRefreshToken,
    AuthRefreshTokenReuseEvent,
    AuthSession,
    AuthSessionActorType,
)
from fastapi import BackgroundTasks


class AuthSessionRepository:
    """Database operations for persistent login sessions."""

    @staticmethod
    async def create_session(
        db: AsyncSession,
        session: AuthSession,
    ) -> AuthSession:
        """Create an auth session record."""

        db.add(session)
        await db.flush()
        return session

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AuthSession | None:
        """Fetch an auth session by primary ID."""

        query = select(AuthSession).where(AuthSession.id == session_id)
        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_session_by_jti(
        db: AsyncSession,
        session_jti: str,
        *,
        lock: bool = False,
    ) -> AuthSession | None:
        """Fetch an auth session by session JTI."""

        query = select(AuthSession).where(AuthSession.session_jti == session_jti)
        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_active_sessions_for_actor(
        db: AsyncSession,
        *,
        actor_type: AuthSessionActorType,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> list[AuthSession]:
        """List active sessions for one actor."""

        result = await db.execute(
            select(AuthSession)
            .where(
                AuthSession.actor_type == actor_type,
                AuthSession.actor_id == actor_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.compromised_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.last_used_at.desc().nullslast())
        )
        return list(result.scalars().all())

    @staticmethod
    async def touch_session(
        db: AsyncSession,
        session: AuthSession,
        *,
        last_used_at: datetime,
    ) -> AuthSession:
        """Update the session last-used timestamp."""

        session.last_used_at = last_used_at
        await db.flush()
        return session

    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        session: AuthSession,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> AuthSession:
        """Revoke one auth session."""

        session.revoked_at = revoked_at
        session.revoked_reason = reason
        await db.flush()
        return session

    @staticmethod
    async def mark_session_compromised(
        db: AsyncSession,
        session: AuthSession,
        *,
        background_tasks: BackgroundTasks,
        compromised_at: datetime,
        reason: str = "refresh_reuse_detected",
    ) -> AuthSession:
        """Mark a session as compromised and revoked."""

        session.compromised_at = compromised_at
        session.revoked_at = compromised_at
        session.revoked_reason = reason
        await db.flush()

        return session

    @staticmethod
    async def revoke_all_sessions_for_actor(
        db: AsyncSession,
        *,
        actor_type: AuthSessionActorType,
        actor_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
        exclude_session_id: uuid.UUID | None = None,
    ) -> int:
        """Revoke all active sessions for an actor."""

        query = (
            update(AuthSession)
            .where(
                AuthSession.actor_type == actor_type,
                AuthSession.actor_id == actor_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
                revoked_reason=reason,
            )
        )

        if exclude_session_id is not None:
            query = query.where(AuthSession.id != exclude_session_id)

        result = await db.execute(query)
        return result.rowcount or 0


class AuthRefreshTokenRepository:
    """Database operations for refresh-token rotation."""

    @staticmethod
    async def create_refresh_token(
        db: AsyncSession,
        refresh_token: AuthRefreshToken,
    ) -> AuthRefreshToken:
        """Create a refresh token row."""

        db.add(refresh_token)
        await db.flush()
        return refresh_token

    @staticmethod
    async def get_by_hash(
        db: AsyncSession,
        token_hash: str,
        *,
        lock: bool = False,
    ) -> AuthRefreshToken | None:
        """Fetch a refresh token by its stored hash."""

        query = select(AuthRefreshToken).where(
            AuthRefreshToken.token_hash == token_hash
        )
        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_jti(
        db: AsyncSession,
        token_jti: str,
        *,
        lock: bool = False,
    ) -> AuthRefreshToken | None:
        """Fetch a refresh token by token JTI."""

        query = select(AuthRefreshToken).where(AuthRefreshToken.token_jti == token_jti)
        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_used(
        db: AsyncSession,
        refresh_token: AuthRefreshToken,
        *,
        used_at: datetime,
        replaced_by_token_id: uuid.UUID | None = None,
    ) -> AuthRefreshToken:
        """Mark a refresh token as used after successful rotation."""

        refresh_token.used_at = used_at
        refresh_token.replaced_by_token_id = replaced_by_token_id
        await db.flush()
        return refresh_token

    @staticmethod
    async def revoke_token(
        db: AsyncSession,
        refresh_token: AuthRefreshToken,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> AuthRefreshToken:
        """Revoke one refresh token."""

        refresh_token.revoked_at = revoked_at
        refresh_token.revoked_reason = reason
        await db.flush()
        return refresh_token

    @staticmethod
    async def mark_reuse_detected(
        db: AsyncSession,
        refresh_token: AuthRefreshToken,
        *,
        detected_at: datetime,
    ) -> AuthRefreshTokenReuseEvent:
        """Mark a token reused and append one audit event for this attempt."""

        refresh_token.reuse_detected_at = detected_at
        event = AuthRefreshTokenReuseEvent(
            refresh_token_id=refresh_token.id,
            session_id=refresh_token.session_id,
            detected_at=detected_at,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def revoke_tokens_for_session(
        db: AsyncSession,
        *,
        session_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        """Revoke all unrevoked refresh tokens for a session."""

        result = await db.execute(
            update(AuthRefreshToken)
            .where(
                AuthRefreshToken.session_id == session_id,
                AuthRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
                revoked_reason=reason,
            )
        )
        return result.rowcount or 0
