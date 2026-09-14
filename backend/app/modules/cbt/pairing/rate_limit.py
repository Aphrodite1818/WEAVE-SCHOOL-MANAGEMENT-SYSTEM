"""Redis-backed abuse protection for the public CBT pairing exchange."""

from __future__ import annotations

import hashlib

from app.config.logging import get_logger
from app.core.cache.redis import create_redis_health_client, get_redis
from app.core.exceptions import TooManyRequestsException

logger = get_logger(__name__)

PAIRING_SHORT_LIMIT = 10
PAIRING_SHORT_WINDOW_SECONDS = 5 * 60
PAIRING_HOURLY_LIMIT = 30
PAIRING_HOURLY_WINDOW_SECONDS = 60 * 60


def _subject_digest(ip_address: str | None) -> str:
    normalized = (ip_address or "unknown").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class CBTPairingRateLimiter:
    """Apply fixed-window IP limits before validating a pairing code."""

    @staticmethod
    async def check(*, ip_address: str | None) -> None:
        client = get_redis()
        temporary_client = False
        if client is None:
            client = await create_redis_health_client()
            temporary_client = client is not None
        if client is None:
            return

        subject = _subject_digest(ip_address)
        buckets = (
            ("short", PAIRING_SHORT_LIMIT, PAIRING_SHORT_WINDOW_SECONDS),
            ("hour", PAIRING_HOURLY_LIMIT, PAIRING_HOURLY_WINDOW_SECONDS),
        )

        try:
            for scope, limit, window_seconds in buckets:
                key = f"security:cbt:pairing:{scope}:{subject}"
                count = int(await client.incr(key))
                if count == 1:
                    await client.expire(key, window_seconds)
                if count > limit:
                    ttl = int(await client.ttl(key))
                    raise TooManyRequestsException(
                        detail="Too many pairing attempts. Please try again later.",
                        retry_after=max(ttl, 1),
                        reason="cbt_pairing_attempt_limit",
                        scope="ip",
                    )
        except TooManyRequestsException:
            raise
        except Exception:
            logger.warning("CBT pairing rate-limit check failed", exc_info=True)
        finally:
            if temporary_client:
                await client.aclose()
