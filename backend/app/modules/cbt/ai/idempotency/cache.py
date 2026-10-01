"""Short-lived Redis replay storage for large AI authoring responses."""

from __future__ import annotations

import base64
import gzip
import json
from typing import Any
from uuid import UUID

from redis.exceptions import RedisError

from app.core.cache.redis import get_runtime_redis

AI_REPLAY_TTL_SECONDS = 24 * 60 * 60
AI_REPLAY_KEY_PREFIX = "cbt:ai:idempotency:result"


class AIReplayStoreUnavailableError(RuntimeError):
    """Raised when Redis cannot safely store or retrieve an AI replay body."""


class AIReplayCache:
    @staticmethod
    def _key(record_id: UUID) -> str:
        return f"{AI_REPLAY_KEY_PREFIX}:{record_id}"

    @staticmethod
    def encode(payload: dict[str, Any]) -> str:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return base64.b64encode(gzip.compress(raw)).decode("ascii")

    @staticmethod
    def decode(value: str) -> dict[str, Any]:
        raw = gzip.decompress(base64.b64decode(value.encode("ascii")))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("AI replay payload must be a JSON object")
        return payload

    @classmethod
    async def store(
        cls,
        record_id: UUID,
        payload: dict[str, Any],
        *,
        ttl_seconds: int = AI_REPLAY_TTL_SECONDS,
    ) -> None:
        redis = get_runtime_redis()
        if redis is None:
            raise AIReplayStoreUnavailableError(
                "Redis is unavailable for CBT AI result recovery."
            )
        try:
            await redis.set(
                cls._key(record_id),
                cls.encode(payload),
                ex=ttl_seconds,
            )
        except RedisError as exc:
            raise AIReplayStoreUnavailableError(
                "Redis is unavailable for CBT AI result recovery."
            ) from exc

    @classmethod
    async def load(cls, record_id: UUID) -> dict[str, Any] | None:
        redis = get_runtime_redis()
        if redis is None:
            raise AIReplayStoreUnavailableError(
                "Redis is unavailable for CBT AI result recovery."
            )
        try:
            value = await redis.get(cls._key(record_id))
        except RedisError as exc:
            raise AIReplayStoreUnavailableError(
                "Redis is unavailable for CBT AI result recovery."
            ) from exc
        if value is None:
            return None
        try:
            return cls.decode(value)
        except (ValueError, TypeError, OSError, json.JSONDecodeError):
            return None

    @classmethod
    async def delete(cls, record_id: UUID) -> None:
        redis = get_runtime_redis()
        if redis is None:
            return
        try:
            await redis.delete(cls._key(record_id))
        except RedisError:
            return
