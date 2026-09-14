"""Transaction-scoped serialization for tenant academic lifecycle writes."""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _academic_lifecycle_lock_key(tenant_id: UUID) -> int:
    """Return a stable signed 64-bit advisory-lock key for one tenant."""

    digest = hashlib.sha256(f"academic-lifecycle:{tenant_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def acquire_academic_lifecycle_lock(
    db: AsyncSession,
    *,
    tenant_id: UUID,
) -> None:
    """Serialize academic mutations and session lifecycle transitions per tenant.

    PostgreSQL releases this lock automatically when the surrounding transaction
    commits or rolls back. All structural academic writes and session transitions
    must acquire the same key before checking the current session state so an
    OPEN -> CLOSING transition cannot race a mutation that is about to commit.
    """

    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _academic_lifecycle_lock_key(tenant_id)},
    )
