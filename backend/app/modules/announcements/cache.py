"""Cache keys and invalidation helpers for announcement reads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.cache.base import build_cache_key, hash_params, tenant_prefix
from app.core.cache.manager import CacheManager


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
) -> None:
    await CacheManager.delete_pattern(
        build_cache_key(
            tenant_prefix(str(tenant_id)),
            "announcements",
            "feed",
            actor_type,
            str(actor_id),
            "*",
        )
    )


async def invalidate_announcement_tenant_cache(tenant_id: UUID | str) -> None:
    await CacheManager.delete_pattern(
        build_cache_key(
            tenant_prefix(str(tenant_id)),
            "announcements",
            "*",
        )
    )
