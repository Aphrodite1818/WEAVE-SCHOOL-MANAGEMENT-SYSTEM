"""Canonical auth-identity service with Redis read-through caching."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.base import build_cache_key, global_prefix
from app.core.cache.events import (
    discard_cache_invalidation_events,
    flush_cache_invalidation_events,
    queue_cache_key_invalidation,
)
from app.core.cache.manager import CacheManager
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.auth_identity.repository import AuthIdentityRepository
from app.modules.auth_identity.schemas import (
    AuthIdentityCreate,
    AuthIdentityResponse,
    IdentityResolution,
)

AUTH_IDENTITY_CACHE_TTL_SECONDS = 300
AUTH_IDENTITY_NOT_FOUND_CACHE_TTL_SECONDS = 15
AUTH_IDENTITY_FOUND_FIELD = "found"

logger = logging.getLogger(__name__)


class AuthIdentityService:
    """Create, update, cache, and resolve canonical login identities."""

    ACTOR_LOOKUP_TABLES: dict[ActorType, str] = {
        ActorType.TENANT_ADMIN: "tenant_admins",
        ActorType.TEACHER_ACCOUNT: "teacher_accounts",
        ActorType.STAFF: "staff_accounts",
        ActorType.PARENT_ACCOUNT: "parent_accounts",
        ActorType.STUDENT: "students",
        ActorType.TEACHER: "teacher_accounts",
        ActorType.PARENT: "parent_accounts",
    }

    GLOBAL_ACTOR_TYPES = {
        ActorType.TEACHER_ACCOUNT,
        ActorType.PARENT_ACCOUNT,
        ActorType.TEACHER,
        ActorType.PARENT,
    }
    TENANT_ACTOR_TYPES = {
        ActorType.TENANT_ADMIN,
        ActorType.STAFF,
        ActorType.STUDENT,
    }

    @staticmethod
    async def _build_response(
        db: AsyncSession,
        record: AuthIdentity,
    ) -> AuthIdentityResponse:
        refresh = getattr(db, "refresh", None)
        if refresh is not None:
            await refresh(record)
        return AuthIdentityResponse.model_validate(record)

    @staticmethod
    def _normalize_identifier(
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        cleaned = identifier.strip()
        if identifier_type == IdentifierType.EMAIL:
            return cleaned.casefold()
        if identifier_type == IdentifierType.ADMISSION_NUMBER:
            return cleaned.upper()
        return cleaned

    @staticmethod
    def _validate_actor_scope(
        *,
        actor_type: ActorType,
        tenant_id: uuid.UUID | None,
    ) -> None:
        normalized_type = ActorType(actor_type)
        if normalized_type in AuthIdentityService.GLOBAL_ACTOR_TYPES:
            if tenant_id is not None:
                raise BadRequestException(
                    "Global account identities cannot be tenant-scoped."
                )
            return
        if normalized_type in AuthIdentityService.TENANT_ACTOR_TYPES:
            if tenant_id is None:
                raise BadRequestException(
                    "Tenant actor identities require tenant_id."
                )
            return
        raise BadRequestException("Unsupported auth identity actor type.")

    @staticmethod
    def _build_identifier_cache_key(
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return build_cache_key(
            global_prefix(),
            "auth-identity",
            IdentifierType(identifier_type).value,
            digest,
        )

    @staticmethod
    def _identifier_cache_key(
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        normalized = AuthIdentityService._normalize_identifier(
            identifier,
            identifier_type,
        )
        return AuthIdentityService._build_identifier_cache_key(
            identifier=normalized,
            identifier_type=identifier_type,
        )

    @staticmethod
    def _queue_cache_invalidation(
        db: AsyncSession,
        *keys: str,
    ) -> None:
        queue_cache_key_invalidation(db, *keys)

    @staticmethod
    async def invalidate_after_commit(db: AsyncSession) -> None:
        try:
            await flush_cache_invalidation_events(db)
        except Exception:
            logger.exception(
                "Auth identity post-commit cache invalidation failed"
            )

    @staticmethod
    def discard_pending_invalidations(db: AsyncSession) -> None:
        discard_cache_invalidation_events(db)

    @staticmethod
    async def ensure_identifier_available(
        db: AsyncSession,
        *,
        identifier: str,
        identifier_type: IdentifierType,
        exclude_identity_id: uuid.UUID | None = None,
    ) -> None:
        normalized = AuthIdentityService._normalize_identifier(
            identifier,
            identifier_type,
        )
        if await AuthIdentityRepository.identifier_exists(
            db,
            normalized,
            identifier_type,
            exclude_identity_id,
        ):
            raise ConflictException(
                "This login identifier is already in use."
            )

    @staticmethod
    async def create_for_actor(
        db: AsyncSession,
        *,
        payload: AuthIdentityCreate,
        tenant_id: uuid.UUID | None = None,
    ) -> AuthIdentityResponse:
        actor_type = ActorType(payload.actor_type)
        AuthIdentityService._validate_actor_scope(
            actor_type=actor_type,
            tenant_id=tenant_id,
        )
        normalized = AuthIdentityService._normalize_identifier(
            payload.identifier,
            payload.identifier_type,
        )
        await AuthIdentityService.ensure_identifier_available(
            db,
            identifier=normalized,
            identifier_type=payload.identifier_type,
        )
        if await AuthIdentityRepository.get_by_actor(
            db,
            actor_type,
            payload.actor_id,
        ):
            raise ConflictException(
                "This actor already has a login identity."
            )

        record = AuthIdentity(
            tenant_id=tenant_id,
            identifier=normalized,
            identifier_type=payload.identifier_type,
            actor_type=actor_type,
            actor_id=payload.actor_id,
            is_active=payload.is_active,
        )
        record = await AuthIdentityRepository.create(db, record)
        AuthIdentityService._queue_cache_invalidation(
            db,
            AuthIdentityService._identifier_cache_key(
                identifier=normalized,
                identifier_type=payload.identifier_type,
            ),
        )
        return await AuthIdentityService._build_response(db, record)

    @staticmethod
    async def ensure_for_actor(
        db: AsyncSession,
        *,
        payload: AuthIdentityCreate,
        tenant_id: uuid.UUID | None = None,
    ) -> AuthIdentityResponse:
        actor_type = ActorType(payload.actor_type)
        AuthIdentityService._validate_actor_scope(
            actor_type=actor_type,
            tenant_id=tenant_id,
        )
        normalized = AuthIdentityService._normalize_identifier(
            payload.identifier,
            payload.identifier_type,
        )
        existing = await AuthIdentityRepository.get_by_actor(
            db,
            actor_type,
            payload.actor_id,
        )
        if existing is None:
            return await AuthIdentityService.create_for_actor(
                db,
                payload=payload,
                tenant_id=tenant_id,
            )
        if (
            existing.identifier != normalized
            or existing.identifier_type != payload.identifier_type
            or existing.tenant_id != tenant_id
        ):
            raise ConflictException(
                "This actor already has a different login identity."
            )
        if payload.is_active and not existing.is_active:
            existing.is_active = True
            await AuthIdentityRepository.save(db, existing)
            AuthIdentityService._queue_cache_invalidation(
                db,
                AuthIdentityService._identifier_cache_key(
                    identifier=normalized,
                    identifier_type=payload.identifier_type,
                ),
            )
        return await AuthIdentityService._build_response(db, existing)

    @staticmethod
    def lookup_table_for_actor_type(
        actor_type: ActorType,
    ) -> str:
        return AuthIdentityService.ACTOR_LOOKUP_TABLES[
            ActorType(actor_type)
        ]

    @staticmethod
    async def resolve_identifier(
        db: AsyncSession,
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> IdentityResolution:
        started_at = time.perf_counter()
        normalized = AuthIdentityService._normalize_identifier(
            identifier,
            identifier_type,
        )
        key = AuthIdentityService._build_identifier_cache_key(
            identifier=normalized,
            identifier_type=identifier_type,
        )

        cached = await CacheManager.get_json(key)
        if isinstance(cached, dict):
            if cached.get(AUTH_IDENTITY_FOUND_FIELD) is False:
                raise NotFoundException("Login identity not found.")
            try:
                resolution = IdentityResolution(
                    actor_type=ActorType(cached["actor_type"]),
                    actor_id=uuid.UUID(cached["actor_id"]),
                    tenant_id=(
                        uuid.UUID(cached["tenant_id"])
                        if cached.get("tenant_id")
                        else None
                    ),
                    lookup_table=str(cached["lookup_table"]),
                )
                logger.info(
                    "Auth identity resolution completed",
                    extra={
                        "identity_cache_source": "redis",
                        "identity_resolution_ms": round(
                            (time.perf_counter() - started_at) * 1000,
                            2,
                        ),
                    },
                )
                return resolution
            except (KeyError, TypeError, ValueError):
                await CacheManager.delete(key)

        identity = await AuthIdentityRepository.get_active_by_identifier(
            db,
            normalized,
            identifier_type,
        )
        if identity is None:
            await CacheManager.set_json(
                key=key,
                value={AUTH_IDENTITY_FOUND_FIELD: False},
                ttl=AUTH_IDENTITY_NOT_FOUND_CACHE_TTL_SECONDS,
            )
            raise NotFoundException("Login identity not found.")

        resolution = IdentityResolution(
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
            tenant_id=identity.tenant_id,
            lookup_table=AuthIdentityService.lookup_table_for_actor_type(
                identity.actor_type
            ),
        )
        await CacheManager.set_json(
            key=key,
            value={
                AUTH_IDENTITY_FOUND_FIELD: True,
                "actor_type": identity.actor_type.value,
                "actor_id": str(identity.actor_id),
                "tenant_id": (
                    str(identity.tenant_id)
                    if identity.tenant_id
                    else None
                ),
                "lookup_table": resolution.lookup_table,
            },
            ttl=AUTH_IDENTITY_CACHE_TTL_SECONDS,
        )
        logger.info(
            "Auth identity resolution completed",
            extra={
                "identity_cache_source": "postgresql",
                "identity_resolution_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
            },
        )
        return resolution

    @staticmethod
    async def update_identifier(
        db: AsyncSession,
        *,
        actor_type: ActorType,
        actor_id: uuid.UUID,
        new_identifier: str,
        identifier_type: IdentifierType,
    ) -> AuthIdentityResponse:
        identity = await AuthIdentityRepository.get_by_actor(
            db,
            actor_type,
            actor_id,
        )
        if identity is None:
            raise NotFoundException("Login identity not found.")

        normalized = AuthIdentityService._normalize_identifier(
            new_identifier,
            identifier_type,
        )
        await AuthIdentityService.ensure_identifier_available(
            db,
            identifier=normalized,
            identifier_type=identifier_type,
            exclude_identity_id=identity.id,
        )
        old_key = AuthIdentityService._identifier_cache_key(
            identifier=identity.identifier,
            identifier_type=identity.identifier_type,
        )
        new_key = AuthIdentityService._identifier_cache_key(
            identifier=normalized,
            identifier_type=identifier_type,
        )
        identity.identifier = normalized
        identity.identifier_type = identifier_type
        await AuthIdentityRepository.save(db, identity)
        AuthIdentityService._queue_cache_invalidation(
            db,
            old_key,
            new_key,
        )
        return await AuthIdentityService._build_response(db, identity)

    @staticmethod
    async def deactivate_for_actor(
        db: AsyncSession,
        *,
        actor_type: ActorType,
        actor_id: uuid.UUID,
    ) -> None:
        identity = await AuthIdentityRepository.get_by_actor(
            db,
            actor_type,
            actor_id,
        )
        if identity is None or not identity.is_active:
            return
        identity.is_active = False
        await AuthIdentityRepository.save(db, identity)
        AuthIdentityService._queue_cache_invalidation(
            db,
            AuthIdentityService._identifier_cache_key(
                identifier=identity.identifier,
                identifier_type=identity.identifier_type,
            ),
        )
