"""Exception classes for ASWA."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Error codes for ASWA exceptions."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    @property
    def http_status(self) -> int:
        """Get the HTTP status code for this error."""
        status_map = {
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.UNAUTHORIZED: 401,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.CONFLICT: 409,
            ErrorCode.RATE_LIMITED: 429,
            ErrorCode.INTERNAL_ERROR: 500,
            ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
        }
        return status_map.get(self, 500)


class AswaError(Exception):
    """Base exception for all ASWA errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize AswaError.

        Args:
            code: The error code
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.__cause__ = cause

    def to_api_response(self) -> dict[str, Any]:
        """Convert this error to an API response dict.

        Returns:
            Dictionary containing code, message, and details
        """
        return {
            "code": self.code.value,
            "message": str(self),
            "details": self.details,
        }


class ValidationError(AswaError):
    """Validation error exception."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details, cause)


class NotFoundError(AswaError):
    """Not found error exception."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize NotFoundError.

        Args:
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(ErrorCode.NOT_FOUND, message, details, cause)


class UnauthorizedError(AswaError):
    """Unauthorized error exception."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize UnauthorizedError.

        Args:
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(ErrorCode.UNAUTHORIZED, message, details, cause)


class RateLimitError(AswaError):
    """Rate limit error exception."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize RateLimitError.

        Args:
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(ErrorCode.RATE_LIMITED, message, details, cause)


class ExternalServiceError(AswaError):
    """External service error exception."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize ExternalServiceError.

        Args:
            message: The error message
            details: Additional error details
            cause: The underlying exception
        """
        super().__init__(ErrorCode.EXTERNAL_SERVICE_ERROR, message, details, cause)
