# ========================== #
#     CONFIG/SECURITY.PY     #
# ========================== #

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import uuid

from jose import jwt
from pwdlib import PasswordHash

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plain-text password for secure database storage."""

    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plain-text password matches a stored hash."""

    return password_hash.verify(plain_password, hashed_password)


def hash_otp(otp_code: str) -> str:
    """Hash an OTP code with HMAC-SHA256 using the application secret."""

    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        otp_code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"otp_sha256${digest}"


def verify_otp(otp_code: str, hashed_otp: str) -> bool:
    """Return whether an OTP code matches the stored OTP hash."""

    if hashed_otp.startswith("otp_sha256$"):
        return hmac.compare_digest(hash_otp(otp_code), hashed_otp)

    return password_hash.verify(otp_code, hashed_otp)


def hash_auth_secret(secret: str) -> str:
    """Hash a one-time authentication secret for storage."""

    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"auth_sha256${digest}"


def verify_auth_secret(secret: str, hashed_secret: str) -> bool:
    """Return whether a one-time authentication secret matches the stored hash."""

    if hashed_secret.startswith("auth_sha256$"):
        return hmac.compare_digest(hash_auth_secret(secret), hashed_secret)

    if hashed_secret.startswith("otp_sha256$"):
        return hmac.compare_digest(hash_otp(secret), hashed_secret)

    return password_hash.verify(secret, hashed_secret)


def generate_token_jti() -> str:
    """Generate a unique token/session identifier."""

    return uuid.uuid4().hex


def generate_refresh_token() -> str:
    """Generate a high-entropy raw refresh token.

    This raw value is sent to the client as an HttpOnly cookie.
    It must never be stored directly in the database.
    """

    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    """Hash a refresh token for database storage."""

    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        refresh_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"refresh_sha256${digest}"


def verify_refresh_token(refresh_token: str, hashed_refresh_token: str) -> bool:
    """Return whether a raw refresh token matches a stored refresh-token hash."""

    return hmac.compare_digest(
        hash_refresh_token(refresh_token),
        hashed_refresh_token,
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    *,
    session_jti: str | None = None,
    token_jti: str | None = None,
) -> str:
    """Create and sign a JWT access token.

    Extra claims:
    - token_type: identifies this as an access token.
    - jti: unique ID for this specific access token.
    - sid: session ID/token-family ID when session auth is enabled.

    Keeping data as the first argument preserves your existing call sites.
    """

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(
            minutes=(60 if settings.ENV == "dev" else settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )

    to_encode.update(
        {
            "exp": expire,
            "token_type": "access",
            "jti": token_jti or generate_token_jti(),
        }
    )

    if session_jti is not None:
        to_encode["sid"] = session_jti

    return jwt.encode(
        claims=to_encode,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
