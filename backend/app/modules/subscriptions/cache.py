#==========================#
#        cache.py          #
#==========================#
"""
Cache helpers for subscription entitlements, usage, and billing state.

Important:
- Cache frontend entitlement reads
- System does not rely only on cached usage for critical write enforcement
- Always invalidate this cache after resource-changing writes
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.base import build_cache_key , tenant_prefix
from app.core.cache.events import (
    invalidate_cache_key_now,
    invalidate_cache_pattern_now,
    queue_cache_key_invalidation,
    queue_cache_pattern_invalidation,
)
from app.core.cache.manager import CacheManager
from app.modules.subscriptions.subscription_enums import ResourceLimitCode



def tenant_subscription_cache_prefix(tenant_id : uuid.UUID) -> str:
    """
    Base prefix for all subscription-related cache keys for one tenant

    Output:
        tenant:{tenant_id} : subscription
    """

    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "subscriptions"
    )


def tenant_billing_cache_key(tenant_id: uuid.UUID) -> str:
    """Cache key for the tenant billing/subscription status snapshot."""

    return build_cache_key(
        tenant_subscription_cache_prefix(tenant_id),
        "billing",
    )



def tenant_entitlements_cache_key(tenant_id : uuid.UUID) -> str:
    """
    Cache Key for a tenant's full entitlement response

    This is what the frontend should see to know which modules are locked / unlocked


    Output:
        tenant"{tenant_id}:subscriptions:entitlements
    """

    return build_cache_key(
        tenant_subscription_cache_prefix(tenant_id),
        "entitlements"
    )



def tenant_resource_usage_cache_key(
        tenant_id : uuid.UUID,
        resource : ResourceLimitCode
) -> str:
    """
    Cache Key for one resource usage count

    Example:
        tenant:{tenant_id}:subscriptions:usage:students
    """

    return build_cache_key(
        tenant_subscription_cache_prefix(tenant_id),
        "usage",
        resource.value
    )




def tenant_all_resource_usage_cache_key(tenant_id : uuid.UUID) -> str:
    """
    Cache Key for all resource usage counts

    Example:
        tenant:{tenant_id}:subscriptions:usage:all
    """

    return build_cache_key(
        tenant_subscription_cache_prefix(tenant_id),
        "usage",
        "all"
    )




def tenant_subscription_cache_pattern(tenant_id: uuid.UUID) -> str:
    """
    Pattern used to invalidate all subscription-related cache for one tenant.

    Example:
        tenant:{tenant_id}:subscriptions:*
    """

    return build_cache_key(
        tenant_subscription_cache_prefix(tenant_id),
        "*",
    )


async def get_cached_entitlements(tenant_id: uuid.UUID) -> Any | None:
    return await CacheManager.get_json(
        tenant_entitlements_cache_key(tenant_id)
    )


async def set_cached_entitlements(
    tenant_id: uuid.UUID,
    value: Any,
    ttl: int,
) -> bool:
    return await CacheManager.set_json(
        key=tenant_entitlements_cache_key(tenant_id),
        value=value,
        ttl=ttl,
    )


async def get_cached_billing(tenant_id: uuid.UUID) -> Any | None:
    return await CacheManager.get_json(
        tenant_billing_cache_key(tenant_id)
    )


async def set_cached_billing(
    tenant_id: uuid.UUID,
    value: Any,
    ttl: int,
) -> bool:
    return await CacheManager.set_json(
        key=tenant_billing_cache_key(tenant_id),
        value=value,
        ttl=ttl,
    )


async def get_cached_resource_usage(
    tenant_id: uuid.UUID,
    resource: ResourceLimitCode,
) -> int | None:
    value = await CacheManager.get_json(
        tenant_resource_usage_cache_key(tenant_id, resource)
    )

    if value is None:
        return None

    return int(value)


async def set_cached_resource_usage(
    tenant_id: uuid.UUID,
    resource: ResourceLimitCode,
    value: int,
    ttl: int,
) -> bool:
    return await CacheManager.set_json(
        key=tenant_resource_usage_cache_key(tenant_id, resource),
        value=value,
        ttl=ttl,
    )


async def get_cached_all_resource_usage(
    tenant_id: uuid.UUID,
) -> dict[str, int] | None:
    value = await CacheManager.get_json(
        tenant_all_resource_usage_cache_key(tenant_id)
    )

    if value is None:
        return None

    return {str(key): int(count) for key, count in dict(value).items()}


async def set_cached_all_resource_usage(
    tenant_id: uuid.UUID,
    value: dict[ResourceLimitCode, int] | dict[str, int],
    ttl: int,
) -> bool:
    serializable_value = {
        key.value if isinstance(key, ResourceLimitCode) else str(key): int(count)
        for key, count in value.items()
    }

    return await CacheManager.set_json(
        key=tenant_all_resource_usage_cache_key(tenant_id),
        value=serializable_value,
        ttl=ttl,
    )


async def invalidate_tenant_entitlements_cache(
    tenant_id: uuid.UUID,
    db: AsyncSession | None = None,
) -> bool:
    key = tenant_entitlements_cache_key(tenant_id)
    if db is not None:
        queue_cache_key_invalidation(db, key)
        return True
    return bool(await invalidate_cache_key_now(key))


async def invalidate_tenant_billing_cache(
    tenant_id: uuid.UUID,
    db: AsyncSession | None = None,
) -> bool:
    key = tenant_billing_cache_key(tenant_id)
    if db is not None:
        queue_cache_key_invalidation(db, key)
        return True
    return bool(await invalidate_cache_key_now(key))


async def invalidate_tenant_resource_usage_cache(
    tenant_id: uuid.UUID,
    resource: ResourceLimitCode,
    db: AsyncSession | None = None,
) -> bool:
    key = tenant_resource_usage_cache_key(tenant_id, resource)
    if db is not None:
        queue_cache_key_invalidation(db, key)
        return True
    return bool(await invalidate_cache_key_now(key))


async def invalidate_tenant_all_resource_usage_cache(
    tenant_id: uuid.UUID,
    db: AsyncSession | None = None,
) -> bool:
    key = tenant_all_resource_usage_cache_key(tenant_id)
    if db is not None:
        queue_cache_key_invalidation(db, key)
        return True
    return bool(await invalidate_cache_key_now(key))


async def invalidate_tenant_subscription_cache(
    tenant_id: uuid.UUID,
    db: AsyncSession | None = None,
) -> int:
    """
    Clears every subscription-related cache key for one tenant.

    Use this after:
    - plan change
    - payment success
    - subscription cancellation
    - student/teacher/parent/class/subject creation
    - student/teacher/parent/class/subject deletion
    """

    pattern = tenant_subscription_cache_pattern(tenant_id)
    if db is not None:
        queue_cache_pattern_invalidation(db, pattern)
        return 0
    return await invalidate_cache_pattern_now(pattern)
