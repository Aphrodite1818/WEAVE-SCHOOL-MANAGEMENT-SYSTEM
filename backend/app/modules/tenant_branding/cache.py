"""Redis cache helpers for tenant branding responses."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.cache.base import build_cache_key, tenant_prefix
from app.core.cache.manager import CacheManager


TENANT_BRANDING_CACHE_TTL_SECONDS = 30 * 60


def build_tenant_branding_cache_key(tenant_id: UUID) -> str:
    """Build the cache key for a tenant's effective branding payload."""

    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "branding",
    )


async def get_cached_branding(tenant_id: UUID) -> dict[str, Any] | None:
    """Fetch a cached effective branding response for a tenant."""

    cached_value = await CacheManager.get_json(build_tenant_branding_cache_key(tenant_id))
    if cached_value is None or not isinstance(cached_value, dict):
        return None
    return cached_value


async def set_cached_branding(
    tenant_id: UUID,
    payload: Any,
    *,
    ttl: int = TENANT_BRANDING_CACHE_TTL_SECONDS,
) -> bool:
    """Cache an effective branding response for a tenant."""

    return await CacheManager.set_json(
        build_tenant_branding_cache_key(tenant_id),
        payload,
        ttl,
    )


async def invalidate_tenant_branding(tenant_id: UUID) -> None:
    """Invalidate a tenant branding cache entry."""

    await CacheManager.delete(build_tenant_branding_cache_key(tenant_id))
