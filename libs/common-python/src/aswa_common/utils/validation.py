"""Validation utilities."""

import re
from uuid import UUID

from aswa_common.exceptions import ValidationError

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email(email: str) -> str:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        Validated email address

    Raises:
        ValidationError: If email is invalid
    """
    if not email or not EMAIL_PATTERN.match(email):
        raise ValidationError("Invalid email address format", {"email": email})
    return email


def validate_uuid(value: str) -> UUID:
    """Validate and parse UUID string.

    Args:
        value: UUID string

    Returns:
        UUID object

    Raises:
        ValidationError: If UUID is invalid
    """
    try:
        return UUID(value)
    except (ValueError, AttributeError) as e:
        raise ValidationError("Invalid UUID format", {"uuid": value}) from e


def validate_not_blank(value: str, field_name: str) -> str:
    """Validate that a string is not blank.

    Args:
        value: Value to validate
        field_name: Name of the field

    Returns:
        Validated value

    Raises:
        ValidationError: If value is blank
    """
    if not value or not value.strip():
        raise ValidationError(
            f"{field_name} must not be blank",
            {"fieldName": field_name},
        )
    return value
