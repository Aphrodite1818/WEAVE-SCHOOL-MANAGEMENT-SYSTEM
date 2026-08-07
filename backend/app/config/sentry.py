"""Sentry error monitoring for API and worker processes."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import sentry_sdk
from pydantic import SecretStr
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.config.logging import get_logger
from app.config.settings import EnvironmentType, settings

logger = get_logger(__name__)

_REDACTED = "[Filtered]"

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "cookie",
        "cookies",
        "email",
        "ip_address",
        "parent_email",
        "password",
        "paystack_secret_key",
        "phone",
        "phone_number",
        "refresh_token",
        "secret",
        "set_cookie",
        "smtp_password",
        "student_email",
        "token",
        "twilio_auth_token",
        "username",
    }
)

_SENSITIVE_SUFFIXES = (
    "_access_code",
    "_api_key",
    "_otp",
    "_password",
    "_secret",
    "_setup_code",
    "_token",
)


def _secret_text(value: SecretStr | str | None) -> str | None:
    """Return a stripped secret value without exposing it in logs."""

    if value is None:
        return None

    if isinstance(value, SecretStr):
        value = value.get_secret_value()

    normalized = str(value).strip()
    return normalized or None


def _normalize_key(key: object) -> str:
    """Normalize dictionary keys before privacy matching."""

    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_key(key: object) -> bool:
    """Return whether a key may contain secret or personal information."""

    normalized = _normalize_key(key)
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def _scrub_value(value: Any) -> Any:
    """Recursively remove secrets and direct personal identifiers."""

    if isinstance(value, Mapping):
        return {
            key: _REDACTED if _is_sensitive_key(key) else _scrub_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_scrub_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_scrub_value(item) for item in value)

    return value


def _before_send(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply a final privacy scrub before an event leaves Weave."""

    _ = hint

    try:
        sanitized = dict(event)

        request = sanitized.get("request")
        if isinstance(request, Mapping):
            request_data = dict(request)
            request_data.pop("data", None)
            sanitized["request"] = request_data

        user = sanitized.get("user")
        if isinstance(user, Mapping):
            safe_user = dict(user)
            for key in ("email", "ip_address", "username"):
                safe_user.pop(key, None)
            sanitized["user"] = safe_user

        result = _scrub_value(sanitized)
        return result if isinstance(result, dict) else sanitized

    except Exception:
        logger.exception("Sentry event scrubbing failed; dropping event")
        return None


def _environment_name() -> str:
    """Resolve the environment displayed inside Sentry."""

    return str(getattr(settings.ENV, "value", settings.ENV))


def _release_name() -> str | None:
    """Resolve an explicit or Railway-derived release identifier."""

    configured = (settings.SENTRY_RELEASE or "").strip()
    if configured:
        return configured

    commit_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()
    if not commit_sha:
        return None

    return f"weave@{commit_sha}"


def _deployment_context(service: str) -> dict[str, str]:
    """Return safe Railway deployment metadata."""

    return {
        "service": service,
        "railway_service": os.getenv("RAILWAY_SERVICE_NAME", service),
        "railway_environment": os.getenv(
            "RAILWAY_ENVIRONMENT_NAME",
            _environment_name(),
        ),
        "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", "unknown"),
        "replica_id": os.getenv("RAILWAY_REPLICA_ID", "unknown"),
    }


def _is_sentry_required() -> bool:
    """Return whether Sentry is a startup requirement for this environment."""

    return settings.ENV == EnvironmentType.PRODUCTION


def is_sentry_active() -> bool:
    """Return whether this process has an active Sentry client."""

    return bool(_secret_text(settings.SENTRY_DSN)) and sentry_sdk.is_initialized()


def initialize_sentry(*, service: str) -> bool:
    """Initialize Sentry, failing startup only when production requires it."""

    dsn = _secret_text(settings.SENTRY_DSN)
    required = _is_sentry_required()

    if not dsn:
        message = "Sentry is required in production. Configure SENTRY_DSN."
        if required:
            logger.critical(message, extra={"service": service})
            raise RuntimeError(message)

        logger.info(
            "Sentry disabled: no DSN configured",
            extra={"service": service},
        )
        return False

    environment = _environment_name()
    release = _release_name()

    integrations: list[Any] = [
        LoggingIntegration(
            level=logging.INFO,
            event_level=None,
        )
    ]

    if service == "api":
        integrations.append(FastApiIntegration())

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            server_name=os.getenv("RAILWAY_SERVICE_NAME") or service,
            sample_rate=settings.SENTRY_ERROR_SAMPLE_RATE,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            propagate_traces=settings.SENTRY_TRACES_SAMPLE_RATE > 0,
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            enable_logs=False,
            enable_metrics=False,
            shutdown_timeout=settings.SENTRY_SHUTDOWN_TIMEOUT_SECONDS,
            before_send=_before_send,
            integrations=integrations,
            default_integrations=True,
            auto_enabling_integrations=True,
            in_app_include=["app"],
            debug=settings.SENTRY_DEBUG,
        )

        sentry_sdk.set_tag("service", service)
        sentry_sdk.set_tag("runtime_environment", str(settings.ENV.value))
        sentry_sdk.set_context(
            "deployment",
            _deployment_context(service),
        )

        logger.info(
            "Sentry initialized",
            extra={
                "service": service,
                "sentry_environment": environment,
                "sentry_release": release,
                "traces_sample_rate": settings.SENTRY_TRACES_SAMPLE_RATE,
            },
        )
        return True

    except Exception as exc:
        if required:
            logger.exception(
                "Sentry initialization failed in production",
                extra={"service": service},
            )
            raise RuntimeError(
                "Sentry initialization failed in production; refusing to start."
            ) from exc

        logger.exception(
            "Sentry initialization failed; continuing without Sentry",
            extra={"service": service},
        )
        return False


def capture_exception(
    exc: BaseException,
    *,
    tags: Mapping[str, object] | None = None,
    contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Capture an exception without allowing telemetry failures to escape."""

    if not is_sentry_active():
        return None

    try:
        with sentry_sdk.isolation_scope() as scope:
            for key, value in (tags or {}).items():
                if value is not None:
                    scope.set_tag(key, str(value))

            for name, values in (contexts or {}).items():
                scope.set_context(name, dict(values))

            return sentry_sdk.capture_exception(exc)

    except Exception:
        logger.exception(
            "Sentry exception capture failed; continuing without interruption"
        )
        return None


async def flush_sentry() -> None:
    """Flush queued events during graceful shutdown."""

    if not is_sentry_active():
        return

    try:
        client = sentry_sdk.get_client()
        await client.flush_async(timeout=settings.SENTRY_SHUTDOWN_TIMEOUT_SECONDS)

    except Exception:
        logger.exception("Sentry flush failed during shutdown")
