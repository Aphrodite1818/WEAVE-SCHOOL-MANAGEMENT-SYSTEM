"""Security primitives for CBT actor authorization credentials."""

from __future__ import annotations

import hashlib
import secrets


ACTOR_ACCESS_TOKEN_PREFIX = "wcbt_acc_"
ACTOR_REFRESH_TOKEN_PREFIX = "wcbt_ref_"
ACTOR_TOKEN_BYTES = 32


def generate_actor_access_token() -> str:
    """Generate one high-entropy opaque CBT actor access token."""

    return f"{ACTOR_ACCESS_TOKEN_PREFIX}{secrets.token_urlsafe(ACTOR_TOKEN_BYTES)}"


def generate_actor_refresh_token() -> str:
    """Generate one high-entropy opaque CBT actor refresh token."""

    return f"{ACTOR_REFRESH_TOKEN_PREFIX}{secrets.token_urlsafe(ACTOR_TOKEN_BYTES)}"


def hash_actor_token(token: str) -> str:
    """Return the SHA-256 fingerprint persisted by Weave for an opaque actor token."""

    if not token:
        raise ValueError("CBT actor token is required")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
