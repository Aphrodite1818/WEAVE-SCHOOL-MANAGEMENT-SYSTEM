# ====================================== #
#       auth_identity/service.py         #
# ====================================== #

"""Auth identity service layer."""

import hashlib
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.base import build_cache_key, global_prefix
from app.core.cache.manager import CacheManager
from app.core.cache.redis import get_redis
from app.core.exceptions import ConflictException, NotFoundException
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
AUTH_IDENTITY_PENDING_INVALIDATIONS = "auth_identity_pending_invalidations"

logger = logging.getLogger(__name__)


class AuthIdentityService:
    """Business logic for creating and resolving login identities."""

    @staticmethod
    def _normalize_identifier(
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        """Normalize login identifier before storing or querying."""

        cleaned_identifier = identifier.strip()

        if identifier_type == IdentifierType.EMAIL:
            return cleaned_identifier.lower()

        if identifier_type == IdentifierType.ADMISSION_NUMBER:
            return cleaned_identifier.upper()

        return cleaned_identifier

    @staticmethod
    def _build_identifier_cache_key(
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        """
        Build a privacy-safe cache key for a normalized login identifier.

        Raw email addresses and admission numbers must never appear in Redis keys.
        """

        identifier_digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()

        return build_cache_key(
            global_prefix(),
            "auth-identity",
            IdentifierType(identifier_type).value,
            identifier_digest,
        )

    @staticmethod
    def _serialize_resolution(
        resolution: IdentityResolution,
    ) -> dict[str, str | bool]:
        """Convert an identity resolution into a Redis-safe payload."""

        return {
            AUTH_IDENTITY_FOUND_FIELD: True,
            "actor_type": ActorType(resolution.actor_type).value,
            "actor_id": str(resolution.actor_id),
            "tenant_id": str(resolution.tenant_id),
        }

    @staticmethod
    def _deserialize_resolution(
        payload: object,
    ) -> IdentityResolution | None:
        """
        Validate and convert cached identity data.

        Invalid cache values must be treated as cache misses.
        """

        if not isinstance(payload, dict):
            return None

        if payload.get(AUTH_IDENTITY_FOUND_FIELD) is not True:
            return None

        actor_type = payload.get("actor_type")
        actor_id = payload.get("actor_id")
        tenant_id = payload.get("tenant_id")

        if not all(
            isinstance(value, str) for value in (actor_type, actor_id, tenant_id)
        ):
            return None

        try:
            return IdentityResolution(
                actor_type=ActorType(actor_type),
                actor_id=uuid.UUID(actor_id),
                tenant_id=uuid.UUID(tenant_id),
            )
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _identifier_cache_key(
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> str:
        """Return the privacy-safe cache key for one identifier."""

        normalized_identifier = AuthIdentityService._normalize_identifier(
            identifier=identifier,
            identifier_type=identifier_type,
        )

        return AuthIdentityService._build_identifier_cache_key(
            identifier=normalized_identifier,
            identifier_type=identifier_type,
        )

    @staticmethod
    def _queue_cache_invalidation(db: AsyncSession, *keys: str) -> None:
        """Attach invalidations to the current transaction without touching Redis."""

        pending = db.sync_session.info.setdefault(
            AUTH_IDENTITY_PENDING_INVALIDATIONS, set()
        )
        pending.update(keys)

    @staticmethod
    async def invalidate_after_commit(db: AsyncSession) -> None:
        """Delete keys queued by a transaction, after its successful commit."""

        keys = tuple(
            db.sync_session.info.pop(AUTH_IDENTITY_PENDING_INVALIDATIONS, set())
        )
        if not keys:
            return

        try:
            await CacheManager.delete_many(list(keys))
        except Exception:
            # PostgreSQL already committed and remains authoritative. Never turn a
            # successful write into an API failure because Redis is unavailable.
            logger.exception("Auth identity post-commit cache invalidation failed")

    @staticmethod
    def discard_pending_invalidations(db: AsyncSession) -> None:
        """Discard keys belonging to a transaction that was rolled back."""

        db.sync_session.info.pop(AUTH_IDENTITY_PENDING_INVALIDATIONS, None)

    @staticmethod
    async def ensure_identifier_available(
        db: AsyncSession,
        *,
        identifier: str,
        identifier_type: IdentifierType,
        exclude_identity_id: uuid.UUID | None = None,
    ) -> None:
        """Ensure a login identifier is not already assigned to another actor."""

        normalized_identifier = AuthIdentityService._normalize_identifier(
            identifier=identifier,
            identifier_type=identifier_type,
        )

        exists = await AuthIdentityRepository.identifier_exists(
            db=db,
            identifier=normalized_identifier,
            identifier_type=identifier_type,
            exclude_identity_id=exclude_identity_id,
        )

        if exists:
            raise ConflictException("This login identifier is already in use.")

    @staticmethod
    async def create_for_actor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: AuthIdentityCreate,
    ) -> AuthIdentityResponse:
        """Create a login identity for an actor."""

        normalized_identifier = AuthIdentityService._normalize_identifier(
            identifier=payload.identifier,
            identifier_type=payload.identifier_type,
        )

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_identifier,
            identifier_type=payload.identifier_type,
        )

        existing_actor_identity = await AuthIdentityRepository.get_by_actor(
            db=db,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
        )

        if existing_actor_identity is not None:
            raise ConflictException("This actor already has a login identity.")

        identity = AuthIdentity(
            tenant_id=tenant_id,
            identifier=normalized_identifier,
            identifier_type=payload.identifier_type,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            is_active=payload.is_active,
        )

        created_identity = await AuthIdentityRepository.create(
            db=db,
            record=identity,
        )

        AuthIdentityService._queue_cache_invalidation(
            db,
            AuthIdentityService._identifier_cache_key(
                identifier=normalized_identifier,
                identifier_type=payload.identifier_type,
            ),
        )

        return AuthIdentityResponse.model_validate(created_identity)

    @staticmethod
    async def resolve_identifier(
        db: AsyncSession,
        *,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> IdentityResolution:
        """
        Resolve a login identifier through Redis first and PostgreSQL on cache miss.

        PostgreSQL remains the source of truth.
        """

        started_at = time.perf_counter()
        cache_source = "postgresql"
        normalized_identifier = AuthIdentityService._normalize_identifier(
            identifier=identifier,
            identifier_type=identifier_type,
        )

        cache_key = AuthIdentityService._build_identifier_cache_key(
            identifier=normalized_identifier,
            identifier_type=identifier_type,
        )

        redis_available = get_redis() is not None
        cached_payload = await CacheManager.get_json(cache_key)

        if isinstance(cached_payload, dict):
            if cached_payload.get(AUTH_IDENTITY_FOUND_FIELD) is False:
                AuthIdentityService._log_resolution_timing(
                    started_at, "redis_negative_hit"
                )
                raise NotFoundException("Login identity not found.")

            cached_resolution = AuthIdentityService._deserialize_resolution(
                cached_payload
            )

            if cached_resolution is not None:
                AuthIdentityService._log_resolution_timing(started_at, "redis_hit")
                return cached_resolution

            cache_source = "postgresql_malformed_cache"
            await CacheManager.delete(cache_key)
        elif not redis_available:
            cache_source = "postgresql_redis_unavailable"

        identity = await AuthIdentityRepository.get_active_by_identifier(
            db=db,
            identifier=normalized_identifier,
            identifier_type=identifier_type,
        )

        if identity is None:
            await CacheManager.set_json(
                key=cache_key,
                value={AUTH_IDENTITY_FOUND_FIELD: False},
                ttl=AUTH_IDENTITY_NOT_FOUND_CACHE_TTL_SECONDS,
            )

            AuthIdentityService._log_resolution_timing(started_at, cache_source)
            raise NotFoundException("Login identity not found.")

        resolution = IdentityResolution(
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
            tenant_id=identity.tenant_id,
        )

        await CacheManager.set_json(
            key=cache_key,
            value=AuthIdentityService._serialize_resolution(resolution),
            ttl=AUTH_IDENTITY_CACHE_TTL_SECONDS,
        )

        AuthIdentityService._log_resolution_timing(started_at, cache_source)
        return resolution

    @staticmethod
    def _log_resolution_timing(started_at: float, cache_source: str) -> None:
        logger.info(
            "Auth identity resolution completed",
            extra={
                "identity_cache_source": cache_source,
                "identity_resolution_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )

    @staticmethod
    async def update_identifier(
        db: AsyncSession,
        *,
        actor_type: ActorType,
        actor_id: uuid.UUID,
        new_identifier: str,
        identifier_type: IdentifierType,
    ) -> AuthIdentityResponse:
        """Update the login identifier attached to an actor."""

        identity = await AuthIdentityRepository.get_by_actor(
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        if identity is None:
            raise NotFoundException("Login identity not found.")

        old_identifier = identity.identifier
        old_identifier_type = identity.identifier_type

        normalized_identifier = AuthIdentityService._normalize_identifier(
            identifier=new_identifier,
            identifier_type=identifier_type,
        )

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_identifier,
            identifier_type=identifier_type,
            exclude_identity_id=identity.id,
        )

        identity.identifier = normalized_identifier
        identity.identifier_type = identifier_type

        updated_identity = await AuthIdentityRepository.save(
            db=db,
            record=identity,
        )

        old_cache_key = AuthIdentityService._build_identifier_cache_key(
            identifier=AuthIdentityService._normalize_identifier(
                identifier=old_identifier,
                identifier_type=old_identifier_type,
            ),
            identifier_type=old_identifier_type,
        )

        new_cache_key = AuthIdentityService._build_identifier_cache_key(
            identifier=normalized_identifier,
            identifier_type=identifier_type,
        )

        AuthIdentityService._queue_cache_invalidation(
            db, old_cache_key, new_cache_key
        )

        return AuthIdentityResponse.model_validate(updated_identity)

    @staticmethod
    async def deactivate_for_actor(
        db: AsyncSession,
        *,
        actor_type: ActorType,
        actor_id: uuid.UUID,
    ) -> AuthIdentityResponse:
        """Deactivate an actor login identity."""

        identity = await AuthIdentityRepository.get_by_actor(
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        if identity is None:
            raise NotFoundException("Login identity not found.")

        identifier = identity.identifier
        identifier_type = identity.identifier_type

        deactivated_identity = await AuthIdentityRepository.deactivate(db, identity)

        AuthIdentityService._queue_cache_invalidation(
            db,
            AuthIdentityService._identifier_cache_key(
                identifier=identifier,
                identifier_type=identifier_type,
            ),
        )

        return AuthIdentityResponse.model_validate(deactivated_identity)

    @staticmethod
    async def get_identity_for_actor(
        db: AsyncSession,
        *,
        actor_type: ActorType,
        actor_id: uuid.UUID,
    ) -> AuthIdentityResponse:
        """Return the login identity attached to an actor."""

        identity = await AuthIdentityRepository.get_by_actor(
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        if identity is None:
            raise NotFoundException("Login identity not found.")

        return AuthIdentityResponse.model_validate(identity)


"""NB: This service does not commit."""
