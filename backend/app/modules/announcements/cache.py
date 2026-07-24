"""Cache keys and invalidation helpers for announcement reads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.base import build_cache_key, hash_params, tenant_prefix
from app.core.cache.events import (
    invalidate_cache_pattern_now,
    queue_cache_pattern_invalidation,
)


def announcement_feed_cache_key(
    tenant_id: UUID,
    actor_type: str,
    actor_id: UUID,
    params: dict[str, Any] | None = None,
) -> str:
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "announcements",
        "feed",
        actor_type,
        str(actor_id),
        hash_params(params),
    )


def announcement_manageable_cache_key(
    tenant_id: UUID | str,
    actor_type: str,
    actor_id: UUID,
    params: dict[str, Any] | None = None,
) -> str:
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "announcements",
        "manageable",
        actor_type,
        str(actor_id),
        hash_params(params),
    )


def announcement_detail_cache_key(
    tenant_id: UUID | str,
    actor_type: str,
    actor_id: UUID,
    announcement_id: UUID,
) -> str:
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "announcements",
        "detail",
        actor_type,
        str(actor_id),
        str(announcement_id),
    )


async def invalidate_announcement_actor_cache(
    tenant_id: UUID,
    actor_type: str,
    actor_id: UUID,
    db: AsyncSession | None = None,
) -> None:
    pattern = build_cache_key(
        tenant_prefix(str(tenant_id)),
        "announcements",
        "feed",
        actor_type,
        str(actor_id),
        "*",
    )
    if db is not None:
        queue_cache_pattern_invalidation(db, pattern)
        return
    await invalidate_cache_pattern_now(pattern)


async def invalidate_announcement_tenant_cache(
    tenant_id: UUID | str,
    db: AsyncSession | None = None,
) -> None:
    pattern = build_cache_key(
        tenant_prefix(str(tenant_id)),
        "announcements",
        "*",
    )
    if db is not None:
        queue_cache_pattern_invalidation(db, pattern)
        return
    await invalidate_cache_pattern_now(pattern)
