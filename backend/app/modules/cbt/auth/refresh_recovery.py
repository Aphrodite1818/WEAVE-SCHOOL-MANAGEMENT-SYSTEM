"""Encrypted Redis recovery receipts for CBT actor-token rotation.

Refresh tokens are single-use. A CBT server can therefore lose the response to a
successful rotation and be left holding a token that Weave has already consumed.
This module makes that one logical refresh operation safely replayable without
turning consumed refresh tokens into generally reusable credentials.

PostgreSQL remains authoritative for authorization state. Redis only stores the
short-lived encrypted response needed to recover from an ambiguous network
failure.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config.logging import get_logger
from app.config.settings import settings
from app.core.cache.redis import get_runtime_redis
from app.modules.cbt.auth.schemas import CBTActorTokenPair

logger = get_logger(__name__)

_RECOVERY_VERSION = 1
_RECOVERY_KEY_PREFIX = "cbt:actor-refresh:recovery"
_HKDF_SALT = b"weave-cbt-refresh-recovery-v1"
_HKDF_INFO = b"weave/cbt/actor-refresh/recovery"


class CBTRefreshRecoveryUnavailable(RuntimeError):
    """Raised when refresh recovery state cannot be read or written safely."""


@lru_cache(maxsize=1)
def _derived_keys() -> tuple[bytes, bytes]:
    """Derive independent AES-GCM and HMAC keys from Weave's root secret.

    HKDF domain separation means the JWT/root secret is never used directly as
    either an encryption key or request-fingerprint key.
    """

    root_secret = settings.SECRET_KEY.encode("utf-8")
    key_material = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(root_secret)
    return key_material[:32], key_material[32:]


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def _redis_key(authorization_id: UUID) -> str:
    # One current recovery receipt per authorization family. A successful new
    # rotation overwrites the previous receipt because presenting the replacement
    # refresh token proves the CBT server recovered the prior result.
    return f"{_RECOVERY_KEY_PREFIX}:{authorization_id}"


def _associated_data(*, authorization_id: UUID, idempotency_key: UUID) -> bytes:
    return (
        f"v={_RECOVERY_VERSION}|authorization={authorization_id}|operation={idempotency_key}"
    ).encode("utf-8")


class CBTActorRefreshRecoveryService:
    """Persist and recover one encrypted actor-refresh result in Redis."""

    @staticmethod
    def build_request_fingerprint(
        *,
        server_id: UUID,
        authorization_id: UUID,
        refresh_token_hash: str,
        idempotency_key: UUID,
    ) -> str:
        """Return a keyed fingerprint binding a receipt to one exact refresh action."""

        _, fingerprint_key = _derived_keys()
        message = (
            f"server={server_id}|authorization={authorization_id}|"
            f"refresh={refresh_token_hash}|operation={idempotency_key}"
        ).encode("utf-8")
        return hmac.new(fingerprint_key, message, hashlib.sha256).hexdigest()

    @staticmethod
    async def store(
        *,
        server_id: UUID,
        authorization_id: UUID,
        refresh_token_hash: str,
        idempotency_key: UUID,
        token_pair: CBTActorTokenPair,
        ttl_seconds: int,
    ) -> None:
        """Encrypt and store the result before the old refresh token is consumed."""

        if ttl_seconds <= 0:
            raise ValueError("Refresh recovery TTL must be positive")

        redis = get_runtime_redis()
        if redis is None:
            raise CBTRefreshRecoveryUnavailable("Redis is unavailable for CBT refresh recovery")

        encryption_key, _ = _derived_keys()
        nonce = os.urandom(12)
        aad = _associated_data(
            authorization_id=authorization_id,
            idempotency_key=idempotency_key,
        )
        plaintext = token_pair.model_dump_json().encode("utf-8")
        ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, aad)
        fingerprint = CBTActorRefreshRecoveryService.build_request_fingerprint(
            server_id=server_id,
            authorization_id=authorization_id,
            refresh_token_hash=refresh_token_hash,
            idempotency_key=idempotency_key,
        )
        payload = json.dumps(
            {
                "version": _RECOVERY_VERSION,
                "operation_id": str(idempotency_key),
                "request_fingerprint": fingerprint,
                "nonce": _b64encode(nonce),
                "ciphertext": _b64encode(ciphertext),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

        try:
            await redis.set(
                _redis_key(authorization_id),
                payload,
                ex=ttl_seconds,
            )
        except Exception as exc:
            logger.exception(
                "Failed to persist CBT actor refresh recovery receipt",
                extra={"authorization_id": str(authorization_id)},
            )
            raise CBTRefreshRecoveryUnavailable(
                "Redis is unavailable for CBT refresh recovery"
            ) from exc

    @staticmethod
    async def recover(
        *,
        server_id: UUID,
        authorization_id: UUID,
        refresh_token_hash: str,
        idempotency_key: UUID,
    ) -> CBTActorTokenPair | None:
        """Return the prior result only when the exact logical refresh matches.

        ``None`` means Redis is healthy but there is no matching recovery receipt.
        Redis/decryption failures raise ``CBTRefreshRecoveryUnavailable`` so the
        caller does not mistake infrastructure failure for malicious token reuse.
        """

        redis = get_runtime_redis()
        if redis is None:
            raise CBTRefreshRecoveryUnavailable("Redis is unavailable for CBT refresh recovery")

        try:
            raw_receipt = await redis.get(_redis_key(authorization_id))
        except Exception as exc:
            logger.exception(
                "Failed to read CBT actor refresh recovery receipt",
                extra={"authorization_id": str(authorization_id)},
            )
            raise CBTRefreshRecoveryUnavailable(
                "Redis is unavailable for CBT refresh recovery"
            ) from exc

        if raw_receipt is None:
            return None

        try:
            receipt = json.loads(raw_receipt)
            if receipt.get("version") != _RECOVERY_VERSION:
                raise ValueError("Unsupported CBT refresh recovery receipt version")

            expected_fingerprint = CBTActorRefreshRecoveryService.build_request_fingerprint(
                server_id=server_id,
                authorization_id=authorization_id,
                refresh_token_hash=refresh_token_hash,
                idempotency_key=idempotency_key,
            )
            stored_fingerprint = str(receipt["request_fingerprint"])
            stored_operation = str(receipt["operation_id"])

            if stored_operation != str(idempotency_key) or not hmac.compare_digest(
                stored_fingerprint,
                expected_fingerprint,
            ):
                return None

            encryption_key, _ = _derived_keys()
            nonce = _b64decode(str(receipt["nonce"]))
            ciphertext = _b64decode(str(receipt["ciphertext"]))
            aad = _associated_data(
                authorization_id=authorization_id,
                idempotency_key=idempotency_key,
            )
            plaintext = AESGCM(encryption_key).decrypt(nonce, ciphertext, aad)
            return CBTActorTokenPair.model_validate_json(plaintext)
        except CBTRefreshRecoveryUnavailable:
            raise
        except Exception as exc:
            logger.exception(
                "CBT actor refresh recovery receipt is unreadable",
                extra={"authorization_id": str(authorization_id)},
            )
            raise CBTRefreshRecoveryUnavailable(
                "CBT refresh recovery receipt could not be validated"
            ) from exc

    @staticmethod
    async def delete_best_effort(*, authorization_id: UUID) -> None:
        """Remove stale recovery state without making the primary flow fail."""

        redis = get_runtime_redis()
        if redis is None:
            return
        try:
            await redis.unlink(_redis_key(authorization_id))
        except Exception:
            logger.exception(
                "Failed to delete stale CBT actor refresh recovery receipt",
                extra={"authorization_id": str(authorization_id)},
            )
