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
    def __init__(self, detail: str = "Too many requests", retry_after: int = 60) -> None:
        """Initialize the TooManyRequestsException instance."""
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )
        self.retry_after = retry_after

class ConflictException(AppException):
    """Raised when a conflicting resource already exists."""
    def __init__(self, detail: str = "Resource conflict") -> None:
        """Initialize the ConflictException instance."""
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)




class ImportParserError(ValueError):
    """Raised when an import file cannot be parsed safely"""


    

class ImportTemplateNotFoundError(ValueError):
    """Raised when a template does not exist for a resource type"""




class ImportChunkingError(ValueError):
    """Rased when import chunking receives invalid input"""