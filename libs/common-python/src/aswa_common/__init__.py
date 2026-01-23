"""ASWA Common Python Library - Shared utilities and models."""

from aswa_common.exceptions import (
    AswaError,
    ErrorCode,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from aswa_common.logging.setup import LoggerContextVar, configure_logging, get_logger
from aswa_common.models import (
    ApiError,
    ApiResponse,
    NormalizedDocument,
    PageRequest,
    PageResponse,
    TenantContext,
)

__version__ = "0.1.0"

__all__ = [
    # Exceptions
    "AswaError",
    "ErrorCode",
    "ValidationError",
    "NotFoundError",
    "UnauthorizedError",
    "RateLimitError",
    "ExternalServiceError",
    # Models
    "TenantContext",
    "ApiResponse",
    "ApiError",
    "PageRequest",
    "PageResponse",
    "NormalizedDocument",
    # Logging
    "configure_logging",
    "get_logger",
    "LoggerContextVar",
]
