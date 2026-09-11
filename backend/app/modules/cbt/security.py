# ====================================== #
#           cbt/security.py              #
# ====================================== #

"""Security primitives for the CBT integration domain."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config.settings import settings


PAIRING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_CODE_LENGTH = 8

SERVER_TOKEN_PREFIX = "wcbt_srv_"
SERVER_TOKEN_BYTES = 32


def generate_pairing_code() -> str:
    """
    Generate a short human-friendly one-time CBT pairing code.

    Example:
        7RJM-K4TP
    """

    raw_code = "".join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))

    return f"{raw_code[:4]}-{raw_code[4:]}"


def normalize_pairing_code(code: str) -> str:
    """
    Normalize a pairing code before hashing or comparison.

    Example:
        "7rjm-k4tp" -> "7RJMK4TP"
    """

    normalized = code.strip().upper().replace("-", "").replace(" ", "")

    if len(normalized) != PAIRING_CODE_LENGTH:
        raise ValueError("Invalid CBT pairing code format.")

    if any(character not in PAIRING_CODE_ALPHABET for character in normalized):
        raise ValueError("Invalid CBT pairing code format.")

    return normalized


def hash_pairing_code(code: str) -> str:
    """
    Create a keyed digest of a CBT pairing code for database storage.

    Pairing codes have relatively low entropy because humans must type them,
    so HMAC-SHA256 is used rather than plain SHA-256.
    """

    normalized = normalize_pairing_code(code)

    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"cbt_pairing:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return digest


def verify_pairing_code(
    code: str,
    stored_hash: str,
) -> bool:
    """Return whether a pairing code matches its stored digest."""

    try:
        candidate_hash = hash_pairing_code(code)
    except ValueError:
        return False

    return hmac.compare_digest(
        candidate_hash,
        stored_hash,
    )


def generate_server_token() -> str:
    """
    Generate a high-entropy authentication token for a CBT server.

    The raw token is returned to the CBT server once and must never be
    persisted in plaintext by Weave.
    """

    secret = secrets.token_urlsafe(SERVER_TOKEN_BYTES)

    return f"{SERVER_TOKEN_PREFIX}{secret}"


def hash_server_token(server_token: str) -> str:
    """
    Hash a CBT server token for database storage.

    Server tokens contain at least 256 bits of cryptographically secure
    randomness, so SHA-256 is sufficient for storing their digest.
    """

    return hashlib.sha256(server_token.encode("utf-8")).hexdigest()


def verify_server_token(
    server_token: str,
    stored_hash: str,
) -> bool:
    """Return whether a raw CBT server token matches its stored digest."""

    candidate_hash = hash_server_token(server_token)

    return hmac.compare_digest(
        candidate_hash,
        stored_hash,
    )


def secure_compare(
    value_a: str,
    value_b: str,
) -> bool:
    """Compare two strings using constant-time comparison."""

    return hmac.compare_digest(
        value_a,
        value_b,
    )
