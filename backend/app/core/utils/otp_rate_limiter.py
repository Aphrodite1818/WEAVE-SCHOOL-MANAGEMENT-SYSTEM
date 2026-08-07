from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Self

from redis import Redis
from redis.exceptions import RedisError

from app.config.settings import settings
from app.core.rate_limits.keys import build_rate_limit_key, digest_key_part


@dataclass(frozen=True)
class _SyncRateLimitRule:
    key: str
    limit: int
    window_seconds: int


class OTPRateLimiter:
    """Distributed OTP request limiter with a safe in-memory fallback."""

    _instance = None
    _lock = Lock()
    _records: defaultdict[str, list[float]]
    _redis_client: Redis | None

    def __new__(cls) -> Self:
        """Create or return the singleton instance."""

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._records = defaultdict(list)
                    inst._redis_client = None
                    cls._instance = inst
        return cls._instance

    def _get_redis_client(self) -> Redis | None:
        """Return the shared Redis client when distributed limiting is configured."""

        if not settings.RATE_LIMIT_ENABLED:
            return None

        if self._redis_client is not None:
            return self._redis_client

        redis_url = settings.RATE_LIMIT_REDIS_URL or settings.REDIS_URL
        if not redis_url:
            return None

        self._redis_client = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
            health_check_interval=30,
        )
        return self._redis_client

    def _rules(self, email: str, purpose: str) -> list[_SyncRateLimitRule]:
        """Return the cooldown, burst, and daily OTP request rules."""

        email_hash = digest_key_part(email.strip().lower())
        purpose_value = getattr(purpose, "value", str(purpose))

        return [
            _SyncRateLimitRule(
                key=build_rate_limit_key(
                    "auth",
                    "otp-request",
                    "email",
                    email_hash,
                    purpose_value,
                    "cooldown",
                ),
                limit=1,
                window_seconds=settings.OTP_EMAIL_COOLDOWN_SECONDS,
            ),
            _SyncRateLimitRule(
                key=build_rate_limit_key(
                    "auth",
                    "otp-request",
                    "email",
                    email_hash,
                    purpose_value,
                    "10m",
                ),
                limit=settings.OTP_EMAIL_LIMIT_10M,
                window_seconds=600,
            ),
            _SyncRateLimitRule(
                key=build_rate_limit_key(
                    "auth",
                    "otp-request",
                    "email",
                    email_hash,
                    purpose_value,
                    "24h",
                ),
                limit=settings.OTP_EMAIL_LIMIT_24H,
                window_seconds=86_400,
            ),
        ]

    def _is_allowed_in_memory(self, email: str, purpose: str) -> tuple[bool, int]:
        """Apply all OTP rules locally when Redis is unavailable."""

        purpose_value = getattr(purpose, "value", str(purpose))
        key = f"{email.strip().lower()}:{purpose_value}"
        now = time.time()
        rules = self._rules(email, purpose_value)
        longest_window = max(rule.window_seconds for rule in rules)

        with self._lock:
            timestamps = [
                timestamp for timestamp in self._records[key] if now - timestamp < longest_window
            ]
            self._records[key] = timestamps

            blocked_retry_after = 0

            for rule in rules:
                timestamps_in_window = [
                    timestamp for timestamp in timestamps if now - timestamp < rule.window_seconds
                ]

                if len(timestamps_in_window) >= rule.limit:
                    oldest_relevant = timestamps_in_window[0]
                    retry_after = int(rule.window_seconds - (now - oldest_relevant))
                    blocked_retry_after = max(
                        blocked_retry_after,
                        retry_after,
                        1,
                    )

            if blocked_retry_after > 0:
                return False, blocked_retry_after

            self._records[key].append(now)

        return True, 0

    def _is_allowed_with_redis(
        self,
        redis_client: Redis,
        email: str,
        purpose: str,
    ) -> tuple[bool, int]:
        """Apply OTP request rules using shared Redis counters."""

        rules = self._rules(email, purpose)
        blocked_retry_after = 0

        for rule in rules:
            raw_current = redis_client.get(rule.key)
            current = int(raw_current or 0)

            if current >= rule.limit:
                ttl = redis_client.ttl(rule.key)
                if ttl < 0:
                    ttl = rule.window_seconds
                blocked_retry_after = max(blocked_retry_after, int(ttl))

        if blocked_retry_after > 0:
            return False, max(blocked_retry_after, 1)

        for rule in rules:
            current = int(redis_client.incr(rule.key))
            if current == 1:
                redis_client.expire(rule.key, rule.window_seconds)

            if current > rule.limit:
                ttl = redis_client.ttl(rule.key)
                if ttl < 0:
                    ttl = rule.window_seconds
                blocked_retry_after = max(blocked_retry_after, int(ttl))

        if blocked_retry_after > 0:
            return False, max(blocked_retry_after, 1)

        return True, 0

    def is_allowed(self, email: str, purpose: str) -> tuple[bool, int]:
        """Return whether an OTP request is allowed."""

        if not settings.RATE_LIMIT_ENABLED:
            return True, 0

        redis_client = self._get_redis_client()
        if redis_client is None:
            return self._is_allowed_in_memory(email, purpose)

        try:
            return self._is_allowed_with_redis(
                redis_client,
                email,
                purpose,
            )
        except (RedisError, OSError, ValueError):
            # Preserve OTP availability if Redis is temporarily unreachable while
            # retaining equivalent per-process protection through local counters.
            self._redis_client = None
            return self._is_allowed_in_memory(email, purpose)
