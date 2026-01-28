"""Formatting utilities."""
from datetime import datetime
import re


def format_date(dt: datetime | None, format_str: str = "%B %d, %Y") -> str:
    """Format a datetime.

    Args:
        dt: Datetime to format
        format_str: Format string

    Returns:
        Formatted string
    """
    if dt is None:
        return "Unknown"
    return dt.strftime(format_str)


def format_confidence(confidence: float) -> str:
    """Format confidence score.

    Args:
        confidence: Confidence value (0-1)

    Returns:
        Formatted string
    """
    percentage = int(confidence * 100)

    if percentage >= 80:
        return f"High ({percentage}%)"
    elif percentage >= 50:
        return f"Medium ({percentage}%)"
    else:
        return f"Low ({percentage}%)"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """Escape Markdown special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    special_chars = ["*", "_", "`", "[", "]", "(", ")", "#", "+", "-", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text
