"""Redis-backed cache for report-card readiness derivations.

Readiness is derived state, never authority. Cache failures therefore fail open
and callers always retain the database-backed computation path.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.config.logging import get_logger
from app.core.cache.redis import get_redis

logger = get_logger(__name__)

READINESS_CACHE_VERSION = "v1"
READINESS_CACHE_TTL_SECONDS = 120


def _context_key(
    *,
    tenant_id: UUID,
    student_id: UUID,
    academic_session_id: UUID,
    academic_term_id: UUID,
) -> str:
    return (
        f"report-readiness:{READINESS_CACHE_VERSION}:"
        f"{tenant_id}:{student_id}:{academic_session_id}:{academic_term_id}"
    )


def _session_pattern(
    *,
    tenant_id: UUID,
    student_id: UUID,
    academic_session_id: UUID,
) -> str:
    return (
        f"report-readiness:{READINESS_CACHE_VERSION}:"
        f"{tenant_id}:{student_id}:{academic_session_id}:*"
    )


class ReportReadinessCache:
    """Small fail-open cache for one student/session/term readiness context."""

    @staticmethod
    async def get(
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_session_id: UUID,
        academic_term_id: UUID,
    ) -> dict[str, Any] | None:
        redis = get_redis()
        if redis is None:
            return None
        key = _context_key(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        try:
            raw = await redis.get(key)
            if not raw:
                return None
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except Exception:
            logger.exception("Failed to read report readiness cache.")
            return None

    @staticmethod
    async def set(
        payload: dict[str, Any],
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_session_id: UUID,
        academic_term_id: UUID,
    ) -> None:
        redis = get_redis()
        if redis is None:
            return
        key = _context_key(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        try:
            await redis.set(
                key,
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                ex=READINESS_CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.exception("Failed to write report readiness cache.")

    @staticmethod
    async def invalidate_context(
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_session_id: UUID,
        academic_term_id: UUID,
    ) -> None:
        redis = get_redis()
        if redis is None:
            return
        key = _context_key(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        try:
            await redis.delete(key)
        except Exception:
            logger.exception("Failed to invalidate report readiness cache context.")

    @staticmethod
    async def invalidate_student_session(
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_session_id: UUID,
    ) -> None:
        """Invalidate every term cache entry for one student's session."""

        redis = get_redis()
        if redis is None:
            return
        pattern = _session_pattern(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
        )
        try:
            batch: list[str] = []
            async for key in redis.scan_iter(match=pattern, count=100):
                batch.append(key)
                if len(batch) >= 100:
                    await redis.delete(*batch)
                    batch.clear()
            if batch:
                await redis.delete(*batch)
        except Exception:
            logger.exception("Failed to invalidate report readiness cache session.")
