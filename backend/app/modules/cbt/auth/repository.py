"""Data access for CBT actor authorization and refresh-token state."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.auth.models import (
    CBTActorAuthorization,
    CBTActorRefreshToken,
)


class CBTActorAuthorizationRepository:
    """Persistence operations for CBT actor authorization families."""

    @staticmethod
    async def create(
        db: AsyncSession,
        authorization: CBTActorAuthorization,
    ) -> CBTActorAuthorization:
        db.add(authorization)
        await db.flush()
        return authorization

    @staticmethod
    async def save(
        db: AsyncSession,
        authorization: CBTActorAuthorization,
    ) -> CBTActorAuthorization:
        db.add(authorization)
        await db.flush()
        return authorization

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        authorization_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> CBTActorAuthorization | None:
        query = select(CBTActorAuthorization).where(
            CBTActorAuthorization.id == authorization_id
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_access_token_hash(
        db: AsyncSession,
        token_hash: str,
        *,
        lock: bool = False,
    ) -> CBTActorAuthorization | None:
        query = select(CBTActorAuthorization).where(
            CBTActorAuthorization.access_token_hash == token_hash
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_for_teacher_membership(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        authorization_ids = select(CBTActorAuthorization.id).where(
            CBTActorAuthorization.tenant_id == tenant_id,
            CBTActorAuthorization.teacher_membership_id == membership_id,
            CBTActorAuthorization.revoked_at.is_(None),
        )
        await db.execute(
            update(CBTActorRefreshToken)
            .where(
                CBTActorRefreshToken.authorization_id.in_(authorization_ids),
                CBTActorRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = await db.execute(
            update(CBTActorAuthorization)
            .where(
                CBTActorAuthorization.tenant_id == tenant_id,
                CBTActorAuthorization.teacher_membership_id == membership_id,
                CBTActorAuthorization.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
                revocation_reason=reason[:255],
            )
        )
        return result.rowcount or 0

    @staticmethod
    async def revoke_for_teacher_account(
        db: AsyncSession,
        *,
        teacher_account_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        authorization_ids = select(CBTActorAuthorization.id).where(
            CBTActorAuthorization.teacher_account_id == teacher_account_id,
            CBTActorAuthorization.revoked_at.is_(None),
        )
        await db.execute(
            update(CBTActorRefreshToken)
            .where(
                CBTActorRefreshToken.authorization_id.in_(authorization_ids),
                CBTActorRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = await db.execute(
            update(CBTActorAuthorization)
            .where(
                CBTActorAuthorization.teacher_account_id == teacher_account_id,
                CBTActorAuthorization.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
                revocation_reason=reason[:255],
            )
        )
        return result.rowcount or 0

    @staticmethod
    async def revoke_for_tenant_admin(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        tenant_admin_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        authorization_ids = select(CBTActorAuthorization.id).where(
            CBTActorAuthorization.tenant_id == tenant_id,
            CBTActorAuthorization.tenant_admin_id == tenant_admin_id,
            CBTActorAuthorization.revoked_at.is_(None),
        )
        await db.execute(
            update(CBTActorRefreshToken)
            .where(
                CBTActorRefreshToken.authorization_id.in_(authorization_ids),
                CBTActorRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = await db.execute(
            update(CBTActorAuthorization)
            .where(
                CBTActorAuthorization.tenant_id == tenant_id,
                CBTActorAuthorization.tenant_admin_id == tenant_admin_id,
                CBTActorAuthorization.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at,
                revocation_reason=reason[:255],
            )
        )
        return result.rowcount or 0


class CBTActorRefreshTokenRepository:
    """Persistence operations for opaque rotating CBT actor refresh tokens."""

    @staticmethod
    async def create(
        db: AsyncSession,
        token: CBTActorRefreshToken,
    ) -> CBTActorRefreshToken:
        db.add(token)
        await db.flush()
        return token

    @staticmethod
    async def save(
        db: AsyncSession,
        token: CBTActorRefreshToken,
    ) -> CBTActorRefreshToken:
        db.add(token)
        await db.flush()
        return token

    @staticmethod
    async def get_by_hash(
        db: AsyncSession,
        token_hash: str,
        *,
        lock: bool = False,
    ) -> CBTActorRefreshToken | None:
        query = select(CBTActorRefreshToken).where(
            CBTActorRefreshToken.token_hash == token_hash
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_active_for_authorization(
        db: AsyncSession,
        *,
        authorization_id: uuid.UUID,
        revoked_at: datetime,
    ) -> int:
        result = await db.execute(
            update(CBTActorRefreshToken)
            .where(
                CBTActorRefreshToken.authorization_id == authorization_id,
                CBTActorRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return result.rowcount or 0
