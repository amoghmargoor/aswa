import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import structlog

from .models import TimeRange

logger = structlog.get_logger()


# Relative time patterns
RELATIVE_PATTERNS = {
    r"last\s+(\d+)\s+days?": lambda m: timedelta(days=int(m.group(1))),
    r"last\s+(\d+)\s+weeks?": lambda m: timedelta(weeks=int(m.group(1))),
    r"last\s+(\d+)\s+months?": lambda m: relativedelta(months=int(m.group(1))),
    r"last\s+(\d+)\s+years?": lambda m: relativedelta(years=int(m.group(1))),
    r"past\s+(\d+)\s+days?": lambda m: timedelta(days=int(m.group(1))),
    r"this\s+week": lambda m: "this_week",
    r"this\s+month": lambda m: "this_month",
    r"this\s+quarter": lambda m: "this_quarter",
    r"this\s+year": lambda m: "this_year",
    r"last\s+week": lambda m: "last_week",
    r"last\s+month": lambda m: "last_month",
    r"last\s+quarter": lambda m: "last_quarter",
    r"last\s+year": lambda m: "last_year",
    r"yesterday": lambda m: "yesterday",
    r"today": lambda m: "today",
    r"ytd|year\s+to\s+date": lambda m: "ytd",
    r"qtd|quarter\s+to\s+date": lambda m: "qtd",
    r"mtd|month\s+to\s+date": lambda m: "mtd",
}


class TemporalParser:
    """Parse temporal expressions from queries."""

    def __init__(self):
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), handler)
            for pattern, handler in RELATIVE_PATTERNS.items()
        ]

    def parse(self, query: str) -> TimeRange | None:
        """Parse temporal expressions from query.

        Args:
            query: The query text

        Returns:
            TimeRange or None if no temporal expression found
        """
        # Try relative patterns first
        for pattern, handler in self._compiled_patterns:
            match = pattern.search(query)
            if match:
                result = handler(match)
                return self._resolve_relative(result, match.group())

        # Try explicit date parsing
        return self._parse_explicit_dates(query)

    def _resolve_relative(self, result: timedelta | relativedelta | str, original: str) -> TimeRange:
        """Resolve relative time expression to absolute range."""
        now = datetime.utcnow()

        if isinstance(result, (timedelta, relativedelta)):
            return TimeRange(
                start=now - result,
                end=now,
                relative=original,
                explicit=False,
            )

        # Handle named periods
        if result == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative=original, explicit=False)

        elif result == "yesterday":
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59)
            return TimeRange(start=start, end=end, relative=original, explicit=False)

        elif result == "this_week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative=original, explicit=False)

        elif result == "last_week":
            end = now - timedelta(days=now.weekday() + 1)
            start = end - timedelta(days=6)
            return TimeRange(
                start=start.replace(hour=0, minute=0, second=0, microsecond=0),
                end=end.replace(hour=23, minute=59, second=59),
                relative=original,
                explicit=False,
            )

        elif result == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative=original, explicit=False)

        elif result == "last_month":
            first_of_month = now.replace(day=1)
            end = first_of_month - timedelta(days=1)
            start = end.replace(day=1)
            return TimeRange(
                start=start.replace(hour=0, minute=0, second=0, microsecond=0),
                end=end.replace(hour=23, minute=59, second=59),
                relative=original,
                explicit=False,
            )

        elif result == "this_quarter":
            quarter = (now.month - 1) // 3
            start_month = quarter * 3 + 1
            start = now.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative=original, explicit=False)

        elif result == "this_year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative=original, explicit=False)

        elif result == "ytd":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now, relative="year to date", explicit=False)

        # Default: last 30 days
        return TimeRange(
            start=now - timedelta(days=30),
            end=now,
            relative=original,
            explicit=False,
        )

    def _parse_explicit_dates(self, query: str) -> TimeRange | None:
        """Parse explicit date mentions."""
        # Look for date ranges like "from X to Y"
        range_pattern = r"from\s+(.+?)\s+to\s+(.+?)(?:\s|$)"
        match = re.search(range_pattern, query, re.IGNORECASE)
        if match:
            try:
                start = date_parser.parse(match.group(1), fuzzy=True)
                end = date_parser.parse(match.group(2), fuzzy=True)
                return TimeRange(start=start, end=end, explicit=True)
            except Exception:
                pass

        # Look for "between X and Y"
        between_pattern = r"between\s+(.+?)\s+and\s+(.+?)(?:\s|$)"
        match = re.search(between_pattern, query, re.IGNORECASE)
        if match:
            try:
                start = date_parser.parse(match.group(1), fuzzy=True)
                end = date_parser.parse(match.group(2), fuzzy=True)
                return TimeRange(start=start, end=end, explicit=True)
            except Exception:
                pass

        # Look for single dates with context
        # "in Q1 2024", "in January 2024", etc.
        quarter_pattern = r"(?:in\s+)?Q([1-4])\s*(\d{4})"
        match = re.search(quarter_pattern, query, re.IGNORECASE)
        if match:
            quarter = int(match.group(1))
            year = int(match.group(2))
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            start = datetime(year, start_month, 1)
            if end_month == 12:
                end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = datetime(year, end_month + 1, 1) - timedelta(days=1)
            return TimeRange(start=start, end=end, explicit=True)

        return None
