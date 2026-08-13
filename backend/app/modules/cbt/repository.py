# ====================================== #
#          cbt/repository.py             #
# ====================================== #

"""Data access layer for the CBT integration domain."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.enums import CBTServerStatus
from app.modules.cbt.models import (
    CBTPairingCode,
    CBTServer,
    CBTServerCredential,
)


class CBTServerRepository:
    """Database operations for paired CBT servers."""

    @staticmethod
    async def create(
        db: AsyncSession,
        server: CBTServer,
    ) -> CBTServer:
        """Create a paired CBT server."""

        db.add(server)
        await db.flush()
        return server

    @staticmethod
    async def get_by_tenant_and_id(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        lock: bool = False,
    ) -> CBTServer | None:
        """Fetch one CBT server belonging to a specific tenant."""

        query = select(CBTServer).where(
            CBTServer.id == server_id,
            CBTServer.tenant_id == tenant_id,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_tenant_and_normalized_name(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        normalized_name: str,
        lock: bool = False,
    ) -> CBTServer | None:
        """Fetch one CBT server by its normalized name within a tenant."""

        normalized_name = re.sub(r"\s+", " ", normalized_name.strip()).lower()

        query = select(CBTServer).where(
            CBTServer.tenant_id == tenant_id,
            func.lower(
                func.regexp_replace(
                    func.btrim(CBTServer.name),
                    r"\s+",
                    " ",
                    "g",
                )
            )
            == normalized_name,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[CBTServer]:
        """List all CBT servers belonging to a tenant."""

        result = await db.execute(
            select(CBTServer)
            .where(
                CBTServer.tenant_id == tenant_id,
            )
            .order_by(CBTServer.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def touch_last_seen(
        db: AsyncSession,
        server: CBTServer,
        *,
        seen_at: datetime,
        ip_address: str | None = None,
        client_version: str | None = None,
    ) -> CBTServer:
        """Update diagnostic information after server activity."""

        server.last_seen_at = seen_at

        if ip_address is not None:
            server.last_ip_address = ip_address

        if client_version is not None:
            server.client_version = client_version

        await db.flush()
        return server

    @staticmethod
    async def suspend(
        db: AsyncSession,
        server: CBTServer,
        *,
        suspended_at: datetime,
    ) -> CBTServer:
        """Persist a server suspension."""

        server.status = CBTServerStatus.SUSPENDED
        server.suspended_at = suspended_at

        await db.flush()
        return server

    @staticmethod
    async def reactivate(
        db: AsyncSession,
        server: CBTServer,
    ) -> CBTServer:
        """Persist server reactivation."""

        server.status = CBTServerStatus.ACTIVE
        server.suspended_at = None

        await db.flush()
        return server

    @staticmethod
    async def revoke(
        db: AsyncSession,
        server: CBTServer,
        *,
        revoked_at: datetime,
        revoked_by_admin_id: uuid.UUID,
        reason: str | None = None,
    ) -> CBTServer:
        """Persist permanent server revocation."""

        server.status = CBTServerStatus.REVOKED
        server.revoked_at = revoked_at
        server.revoked_by_admin_id = revoked_by_admin_id
        server.revocation_reason = reason

        await db.flush()
        return server


class CBTServerCredentialRepository:
    """Database operations for CBT server credentials."""

    @staticmethod
    async def create(
        db: AsyncSession,
        credential: CBTServerCredential,
    ) -> CBTServerCredential:
        """Create a server credential."""

        db.add(credential)
        await db.flush()
        return credential

    @staticmethod
    async def get_active_for_server(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        lock: bool = False,
    ) -> CBTServerCredential | None:
        """Fetch the currently active credential for one tenant-owned server."""

        query = (
            select(CBTServerCredential)
            .join(
                CBTServer,
                CBTServer.id == CBTServerCredential.server_id,
            )
            .where(
                CBTServerCredential.server_id == server_id,
                CBTServer.tenant_id == tenant_id,
                CBTServerCredential.revoked_at.is_(None),
            )
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def touch_last_used(
        db: AsyncSession,
        credential: CBTServerCredential,
        *,
        used_at: datetime,
    ) -> CBTServerCredential:
        """Update when a server credential was last used."""

        credential.last_used_at = used_at

        await db.flush()
        return credential

    @staticmethod
    async def revoke_active_for_server(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        server_id: uuid.UUID,
        revoked_at: datetime,
        reason: str | None = None,
    ) -> int:
        """Revoke all active credentials for one tenant-owned server."""

        result = await db.execute(
            update(CBTServerCredential)
            .where(
                CBTServerCredential.server_id == server_id,
                CBTServerCredential.revoked_at.is_(None),
                CBTServerCredential.server_id.in_(
                    select(CBTServer.id).where(
                        CBTServer.id == server_id,
                        CBTServer.tenant_id == tenant_id,
                    )
                ),
            )
            .values(
                revoked_at=revoked_at,
                revocation_reason=reason,
            )
        )

        return result.rowcount or 0


class CBTPairingCodeRepository:
    """Database operations for CBT server pairing codes."""

    @staticmethod
    async def create(
        db: AsyncSession,
        pairing_code: CBTPairingCode,
    ) -> CBTPairingCode:
        """Create a CBT pairing-code record."""

        db.add(pairing_code)
        await db.flush()
        return pairing_code

    @staticmethod
    async def get_by_hash(
        db: AsyncSession,
        code_hash: str,
        *,
        lock: bool = False,
    ) -> CBTPairingCode | None:
        """Fetch a pairing-code record by its stored digest."""

        query = select(CBTPairingCode).where(
            CBTPairingCode.code_hash == code_hash,
        )

        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def invalidate_unused_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int:
        """Invalidate every unused pairing code for a tenant."""

        result = await db.execute(
            update(CBTPairingCode)
            .where(
                CBTPairingCode.tenant_id == tenant_id,
                CBTPairingCode.used_at.is_(None),
                CBTPairingCode.invalidated_at.is_(None),
            )
            .values(
                invalidated_at=invalidated_at,
            )
        )

        return result.rowcount or 0

    @staticmethod
    async def consume(
        db: AsyncSession,
        pairing_code: CBTPairingCode,
        *,
        used_at: datetime,
        server_id: uuid.UUID,
    ) -> CBTPairingCode:
        """Mark a pairing code as consumed by a CBT server."""

        pairing_code.used_at = used_at
        pairing_code.used_by_server_id = server_id

        await db.flush()
        return pairing_code
