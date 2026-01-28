from datetime import datetime
from typing import Any


def format_date(dt: datetime | str) -> str:
    """Format datetime for Slack display.

    Args:
        dt: Datetime or ISO string

    Returns:
        Formatted date string
    """
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

    return dt.strftime("%B %d, %Y at %I:%M %p")


def format_confidence(confidence: float) -> str:
    """Format confidence score.

    Args:
        confidence: Confidence value (0-1)

    Returns:
        Formatted string with indicator
    """
    if confidence >= 0.9:
        return f"High {confidence:.0%}"
    elif confidence >= 0.7:
        return f"Medium {confidence:.0%}"
    else:
        return f"Low {confidence:.0%}"


def format_severity(severity: str) -> str:
    """Format severity with indicator.

    Args:
        severity: Severity level

    Returns:
        Formatted string
    """
    severity_map = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return severity_map.get(severity.lower(), severity)


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def escape_markdown(text: str) -> str:
    """Escape Slack mrkdwn special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    chars = ["*", "_", "~", "`", ">"]
    for char in chars:
        text = text.replace(char, f"\\{char}")
    return text


def format_list(items: list[str], numbered: bool = False) -> str:
    """Format items as a list.

    Args:
        items: List items
        numbered: Use numbers instead of bullets

    Returns:
        Formatted list string
    """
    if numbered:
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    return "\n".join(f"- {item}" for item in items)


def format_key_value(data: dict[str, Any]) -> str:
    """Format dict as key-value pairs.

    Args:
        data: Dictionary to format

    Returns:
        Formatted string
    """
    lines = []
    for key, value in data.items():
        formatted_key = key.replace("_", " ").title()
        lines.append(f"*{formatted_key}:* {value}")
    return "\n".join(lines)
