"""Focused tests for cached authentication identity resolution."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import (
    AUTH_IDENTITY_CACHE_TTL_SECONDS,
    AUTH_IDENTITY_NOT_FOUND_CACHE_TTL_SECONDS,
    AuthIdentityService,
)


ACTOR_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
IDENTITY_ID = uuid.uuid4()
EMAIL = "person@example.com"


def _db() -> SimpleNamespace:
    return SimpleNamespace(sync_session=SimpleNamespace(info={}))


def _identity(identifier: str = EMAIL, *, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=IDENTITY_ID,
        tenant_id=TENANT_ID,
        identifier=identifier,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=ACTOR_ID,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_resolve_identifier_caches_positive_database_result() -> None:
    identity = _identity()

    with (
        patch(
            "app.modules.auth_identity.service.CacheManager.get_json",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.set_json",
            new=AsyncMock(return_value=True),
        ) as set_json,
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_active_by_identifier",
            new=AsyncMock(return_value=identity),
        ) as lookup,
    ):
        result = await AuthIdentityService.resolve_identifier(
            AsyncMock(), identifier=" Person@Example.com ", identifier_type=IdentifierType.EMAIL
        )

    assert result.actor_id == ACTOR_ID
    lookup.assert_awaited_once()
    payload = set_json.await_args.kwargs["value"]
    assert payload == {
        "found": True,
        "actor_type": ActorType.TEACHER.value,
        "actor_id": str(ACTOR_ID),
        "tenant_id": str(TENANT_ID),
    }
    assert set_json.await_args.kwargs["ttl"] == AUTH_IDENTITY_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_resolve_identifier_returns_valid_cached_result_without_database() -> None:
    payload = {
        "found": True,
        "actor_type": ActorType.TEACHER.value,
        "actor_id": str(ACTOR_ID),
        "tenant_id": str(TENANT_ID),
    }

    with (
        patch(
            "app.modules.auth_identity.service.CacheManager.get_json",
            new=AsyncMock(return_value=payload),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_active_by_identifier",
            new=AsyncMock(),
        ) as lookup,
    ):
        result = await AuthIdentityService.resolve_identifier(
            AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
        )

    assert result.actor_id == ACTOR_ID
    assert result.tenant_id == TENANT_ID
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_identifier_negative_cache_avoids_second_database_query() -> None:
    cache: dict[str, object] = {}

    async def get_json(key: str) -> object | None:
        return cache.get(key)

    async def set_json(key: str, value: object, ttl: int) -> bool:
        assert ttl == AUTH_IDENTITY_NOT_FOUND_CACHE_TTL_SECONDS
        cache[key] = value
        return True

    with (
        patch(
            "app.modules.auth_identity.service.CacheManager.get_json",
            new=AsyncMock(side_effect=get_json),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.set_json",
            new=AsyncMock(side_effect=set_json),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_active_by_identifier",
            new=AsyncMock(return_value=None),
        ) as lookup,
    ):
        with pytest.raises(NotFoundException):
            await AuthIdentityService.resolve_identifier(
                AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
            )
        with pytest.raises(NotFoundException):
            await AuthIdentityService.resolve_identifier(
                AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
            )

    lookup.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", [_identity(), None])
async def test_resolve_identifier_falls_back_when_redis_is_unavailable(identity) -> None:
    with (
        patch(
            "app.modules.auth_identity.service.CacheManager.get_json",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.set_json",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_active_by_identifier",
            new=AsyncMock(return_value=identity),
        ),
    ):
        if identity is None:
            with pytest.raises(NotFoundException):
                await AuthIdentityService.resolve_identifier(
                    AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
                )
        else:
            result = await AuthIdentityService.resolve_identifier(
                AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
            )
            assert result.actor_id == ACTOR_ID


@pytest.mark.asyncio
async def test_resolve_identifier_discards_malformed_cache_entry() -> None:
    malformed = {"found": True, "actor_id": "not-a-uuid"}

    with (
        patch(
            "app.modules.auth_identity.service.CacheManager.get_json",
            new=AsyncMock(return_value=malformed),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.delete",
            new=AsyncMock(return_value=True),
        ) as delete,
        patch(
            "app.modules.auth_identity.service.CacheManager.set_json",
            new=AsyncMock(return_value=True),
        ) as set_json,
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_active_by_identifier",
            new=AsyncMock(return_value=_identity()),
        ) as lookup,
    ):
        result = await AuthIdentityService.resolve_identifier(
            AsyncMock(), identifier=EMAIL, identifier_type=IdentifierType.EMAIL
        )

    assert result.actor_id == ACTOR_ID
    delete.assert_awaited_once()
    lookup.assert_awaited_once()
    assert set_json.await_args.kwargs["value"]["found"] is True


@pytest.mark.asyncio
async def test_create_invalidates_negative_identifier_cache() -> None:
    db = _db()
    payload = AuthIdentityCreate(
        identifier=EMAIL,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=ACTOR_ID,
    )

    with (
        patch.object(AuthIdentityService, "ensure_identifier_available", new=AsyncMock()),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_by_actor",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.create",
            new=AsyncMock(return_value=_identity()),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.delete_many",
            new=AsyncMock(return_value=1),
        ) as delete_many,
        patch(
            "app.modules.auth_identity.service.AuthIdentityResponse.model_validate",
            return_value=object(),
        ),
    ):
        await AuthIdentityService.create_for_actor(db, tenant_id=TENANT_ID, payload=payload)
        delete_many.assert_not_awaited()
        await AuthIdentityService.invalidate_after_commit(db)

    delete_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_invalidates_old_positive_and_new_negative_keys() -> None:
    db = _db()
    identity = _identity()
    new_email = "new@example.com"

    with (
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_by_actor",
            new=AsyncMock(return_value=identity),
        ),
        patch.object(AuthIdentityService, "ensure_identifier_available", new=AsyncMock()),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.save",
            new=AsyncMock(return_value=identity),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.delete_many",
            new=AsyncMock(return_value=2),
        ) as delete_many,
        patch(
            "app.modules.auth_identity.service.AuthIdentityResponse.model_validate",
            return_value=object(),
        ),
    ):
        await AuthIdentityService.update_identifier(
            db,
            actor_type=ActorType.TEACHER,
            actor_id=ACTOR_ID,
            new_identifier=new_email,
            identifier_type=IdentifierType.EMAIL,
        )
        delete_many.assert_not_awaited()
        await AuthIdentityService.invalidate_after_commit(db)

    deleted_keys = delete_many.await_args.args[0]
    assert len(deleted_keys) == 2
    assert all(EMAIL not in key and new_email not in key for key in deleted_keys)


@pytest.mark.asyncio
async def test_deactivation_invalidates_positive_identifier_cache() -> None:
    db = _db()
    identity = _identity()

    with (
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_by_actor",
            new=AsyncMock(return_value=identity),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.deactivate",
            new=AsyncMock(return_value=identity),
        ),
        patch(
            "app.modules.auth_identity.service.CacheManager.delete_many",
            new=AsyncMock(return_value=1),
        ) as delete_many,
        patch(
            "app.modules.auth_identity.service.AuthIdentityResponse.model_validate",
            return_value=object(),
        ),
    ):
        await AuthIdentityService.deactivate_for_actor(
            db, actor_type=ActorType.TEACHER, actor_id=ACTOR_ID
        )
        delete_many.assert_not_awaited()
        await AuthIdentityService.invalidate_after_commit(db)

    delete_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_discards_pending_invalidation_without_deleting_cache() -> None:
    db = _db()
    key = AuthIdentityService._identifier_cache_key(
        identifier=EMAIL,
        identifier_type=IdentifierType.EMAIL,
    )
    AuthIdentityService._queue_cache_invalidation(db, key)

    with patch(
        "app.modules.auth_identity.service.CacheManager.delete_many",
        new=AsyncMock(),
    ) as delete_many:
        AuthIdentityService.discard_pending_invalidations(db)
        await AuthIdentityService.invalidate_after_commit(db)

    delete_many.assert_not_awaited()
