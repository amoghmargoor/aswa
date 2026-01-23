"""API response models."""

from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from aswa_common.exceptions import AswaError

T = TypeVar("T")


class ApiError(BaseModel):
    """API error response."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    """Generic API response wrapper."""

    success: bool
    data: T | None = None
    error: ApiError | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str | None = None

    @classmethod
    def ok(cls, data: T, request_id: str | None = None) -> "ApiResponse[T]":
        """Create a successful response.

        Args:
            data: The response data
            request_id: Optional request ID

        Returns:
            Successful ApiResponse
        """
        return cls(success=True, data=data, request_id=request_id)

    @classmethod
    def fail(cls, error: AswaError, request_id: str | None = None) -> "ApiResponse[None]":
        """Create an error response from an AswaError.

        Args:
            error: The error
            request_id: Optional request ID

        Returns:
            Error ApiResponse
        """
        api_error = ApiError(
            code=error.code.value,
            message=str(error),
            details=error.details,
        )
        return cls(success=False, error=api_error, request_id=request_id)


class PageRequest(BaseModel):
    """Pagination request parameters."""

    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_direction: Literal["asc", "desc"] = "desc"


class PageResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    content: list[T]
    total_elements: int
    total_pages: int
    current_page: int
    page_size: int

    @classmethod
    def create(
        cls,
        content: list[T],
        total_elements: int,
        current_page: int,
        page_size: int,
    ) -> "PageResponse[T]":
        """Create a paginated response.

        Args:
            content: The page content
            total_elements: Total number of elements
            current_page: Current page number
            page_size: Page size

        Returns:
            PageResponse instance
        """
        import math

        total_pages = math.ceil(total_elements / page_size) if page_size > 0 else 0
        return cls(
            content=content,
            total_elements=total_elements,
            total_pages=total_pages,
            current_page=current_page,
            page_size=page_size,
        )

    def has_content(self) -> bool:
        """Check if page has content.

        Returns:
            True if page has content
        """
        return len(self.content) > 0

    def has_next(self) -> bool:
        """Check if there is a next page.

        Returns:
            True if there is a next page
        """
        return self.current_page < self.total_pages - 1

    def has_previous(self) -> bool:
        """Check if there is a previous page.

        Returns:
            True if there is a previous page
        """
        return self.current_page > 0
