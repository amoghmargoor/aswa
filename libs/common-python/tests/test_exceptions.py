"""Tests for exception classes."""

import pytest

from aswa_common.exceptions import (
    AswaError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)


def test_error_code_http_status():
    """Test that error codes have correct HTTP status."""
    assert ErrorCode.VALIDATION_ERROR.http_status == 400
    assert ErrorCode.UNAUTHORIZED.http_status == 401
    assert ErrorCode.FORBIDDEN.http_status == 403
    assert ErrorCode.NOT_FOUND.http_status == 404
    assert ErrorCode.CONFLICT.http_status == 409
    assert ErrorCode.RATE_LIMITED.http_status == 429
    assert ErrorCode.INTERNAL_ERROR.http_status == 500
    assert ErrorCode.EXTERNAL_SERVICE_ERROR.http_status == 502


def test_aswa_error_creation():
    """Test AswaError can be created with code and message."""
    error = AswaError(ErrorCode.NOT_FOUND, "Resource not found")
    assert error.code == ErrorCode.NOT_FOUND
    assert str(error) == "Resource not found"
    assert error.details == {}


def test_aswa_error_with_details():
    """Test AswaError can include details."""
    details = {"resource_id": "123", "resource_type": "User"}
    error = AswaError(ErrorCode.NOT_FOUND, "Resource not found", details=details)
    assert error.details == details


def test_aswa_error_to_api_response():
    """Test AswaError converts to API response format."""
    error = AswaError(
        ErrorCode.VALIDATION_ERROR,
        "Invalid email",
        details={"field": "email"},
    )
    api_response = error.to_api_response()

    assert api_response["code"] == "VALIDATION_ERROR"
    assert api_response["message"] == "Invalid email"
    assert api_response["details"] == {"field": "email"}


def test_validation_error():
    """Test ValidationError is properly configured."""
    error = ValidationError("Invalid input")
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.code.http_status == 400


def test_not_found_error():
    """Test NotFoundError is properly configured."""
    error = NotFoundError("Resource not found")
    assert error.code == ErrorCode.NOT_FOUND
    assert error.code.http_status == 404
