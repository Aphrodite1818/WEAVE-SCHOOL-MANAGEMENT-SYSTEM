"""Transaction-scoped serialization for subscription resource quota checks."""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.subscription_enums import ResourceLimitCode


def _quota_lock_key(tenant_id: UUID, resource: ResourceLimitCode) -> int:
    """Return a stable signed 64-bit advisory-lock key for one tenant resource."""

    digest = hashlib.sha256(f"{tenant_id}:{resource.value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def acquire_resource_quota_lock(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    resource: ResourceLimitCode,
) -> None:
    """Serialize quota check + mutation within the current PostgreSQL transaction.

    The lock is released automatically when the surrounding transaction commits
    or rolls back. Call this immediately before the existing resource-limit check
    and keep the protected mutation on the same ``AsyncSession``.
    """

    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _quota_lock_key(tenant_id, resource)},
    )
