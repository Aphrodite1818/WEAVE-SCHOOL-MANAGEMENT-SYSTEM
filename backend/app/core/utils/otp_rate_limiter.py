from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Self

from redis import Redis

from app.config.settings import settings
from app.core.rate_limits.keys import build_rate_limit_key, digest_key_part


class OTPRateLimiter:
    """Distributed OTP request limiter with a safe in-memory fallback."""

    _instance = None
    _lock = Lock()
    _records: defaultdict[str, list[float]]
    _max_requests: int
    _window_seconds: int
    _redis_client: Redis | None

    def __new__(cls) -> Self:
        """Create or return the singleton instance."""

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._records = defaultdict(list)
                    inst._max_requests = settings.OTP_EMAIL_LIMIT_10M
                    inst._window_seconds = 600
                    inst._redis_client = None
                    cls._instance = inst
        return cls._instance

    def _get_redis_client(self) -> Redis | None:
        """Return a sync Redis client for legacy synchronous callers."""

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

    def _redis_key(self, email: str, purpose: str) -> str:
        email_hash = digest_key_part(email.strip().lower())
        purpose_value = getattr(purpose, "value", str(purpose))
        return build_rate_limit_key("auth", "otp-request", "email", email_hash, purpose_value, "10m")

    def _is_allowed_in_memory(self, email: str, purpose: str) -> tuple[bool, int]:
        key = f"{email.strip().lower()}:{purpose}"
        now = time.time()

        self._records[key] = [
            timestamp
            for timestamp in self._records[key]
            if now - timestamp < self._window_seconds
        ]

        current_count = len(self._records[key])
        if current_count >= self._max_requests:
            oldest = self._records[key][0]
            retry_after = int(self._window_seconds - (now - oldest))
            return False, max(retry_after, 1)

        self._records[key].append(now)
        return True, 0

    def is_allowed(self, email: str, purpose: str) -> tuple[bool, int]:
        """Return whether an OTP request is allowed."""

        redis_client = self._get_redis_client()
        if redis_client is None:
            return self._is_allowed_in_memory(email, purpose)

        key = self._redis_key(email, purpose)
        current = int(redis_client.incr(key))
        if current == 1:
            redis_client.expire(key, self._window_seconds)

        ttl = redis_client.ttl(key)
        if ttl < 0:
            ttl = self._window_seconds

        if current > self._max_requests:
            return False, max(int(ttl), 1)

        return True, 0
