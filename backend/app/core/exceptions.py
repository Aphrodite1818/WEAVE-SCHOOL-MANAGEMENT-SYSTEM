#======================================#
#         core/exceptions.py           #
#======================================#

from typing import Any

from fastapi import status

class AppException(Exception):
    """Base class for all custom application exceptions."""
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: dict | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the AppException instance."""
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        self.payload = payload or {}
        super().__init__(self.detail)

class NotFoundException(AppException):
    """Raised when the requested resource is not found."""
    def __init__(self, detail: str = "Resource not found") -> None:
        """Initialize the NotFoundException instance."""
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class BadRequestException(AppException):
    """Raised when the request is invalid."""
    def __init__(self, detail: str = "Bad request") -> None:
        """Initialize the BadRequestException instance."""
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class UnauthorizedException(AppException):
    """Raised when authentication fails."""
    def __init__(self, detail: str = "Unauthorized") -> None:
        """Initialize the UnauthorizedException instance."""
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

class ForbiddenException(AppException):
    """Raised when the current user is not allowed to access a resource."""
    def __init__(self, detail: str = "Forbidden") -> None:
        """Initialize the ForbiddenException instance."""
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class AccountNotVerifiedException(AppException):
    """Raised when an account has not been verified yet."""
    def __init__(
        self,
        detail: str = "Account not verified",
        headers: dict | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the AccountNotVerifiedException instance."""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=headers,
            payload=payload,
        )

class TooManyRequestsException(AppException):
    """Raised when rate limits are exceeded."""
    def __init__(
        self,
        detail: str = "Too many requests",
        retry_after: int = 60,
        *,
        reason: str | None = None,
        scope: str | None = None,
    ) -> None:
        """Initialize the TooManyRequestsException instance."""

        retry_after_seconds = max(int(retry_after), 1)
        payload: dict[str, Any] = {
            "rate_limited": True,
            "retry_after": retry_after_seconds,
            "retry_after_seconds": retry_after_seconds,
            "next_allowed_in_seconds": retry_after_seconds,
        }
        if reason:
            payload["rate_limit_reason"] = reason
        if scope:
            payload["rate_limit_scope"] = scope

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after_seconds)},
            payload=payload,
        )
        self.retry_after = retry_after_seconds
        self.reason = reason
        self.scope = scope

class PlatformMaintenanceException(AppException):
    """Raised when platform lockdown blocks non-superadmin traffic."""

    def __init__(
        self,
        detail: str = "Weave is temporarily in maintenance mode. Please try again later.",
        *,
        reason: str | None = None,
    ) -> None:
        """Initialize the PlatformMaintenanceException instance."""

        payload: dict[str, Any] = {
            "maintenance_mode": True,
            "platform_lockdown": True,
            "retryable": True,
        }
        if reason:
            payload["maintenance_reason"] = reason

        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers={"Retry-After": "60"},
            payload=payload,
        )

class SecurityBlockException(AppException):
    """Raised when a manual IP/network containment rule blocks traffic."""

    def __init__(
        self,
        detail: str = "Access from this network has been temporarily blocked for security reasons.",
        *,
        reason: str | None = None,
        ip_label: str | None = None,
        expires_at: str | None = None,
    ) -> None:
        """Initialize the SecurityBlockException instance."""

        payload: dict[str, Any] = {
            "security_block": True,
            "ip_blocked": True,
            "retryable": True,
            "ip_label": ip_label,
            "reason": reason,
            "expires_at": expires_at,
        }

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers={"Retry-After": "300"},
            payload=payload,
        )

class ConflictException(AppException):
    """Raised when a conflicting resource already exists."""
    def __init__(self, detail: str = "Resource conflict") -> None:
        """Initialize the ConflictException instance."""
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)



class ImportParserError(ValueError):
    """Raised when an import file cannot be parsed safely"""
    pass


class ImportTemplateNotFoundError(ValueError):
    """Raised when an import template is not registered for a resource/file type."""
    pass
