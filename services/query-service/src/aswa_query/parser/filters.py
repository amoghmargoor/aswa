import re
from typing import Any
import structlog

from .models import QueryFilter

logger = structlog.get_logger()


# Filter patterns
FILTER_PATTERNS = [
    # Equality
    (r"(?:where|with|having)\s+(\w+)\s*(?:=|is|equals?)\s*[\"']?([^\"']+)[\"']?", "eq"),
    # Greater than
    (r"(\w+)\s*(?:>|greater than|more than|above)\s*(\d+(?:\.\d+)?)", "gt"),
    # Less than
    (r"(\w+)\s*(?:<|less than|below|under)\s*(\d+(?:\.\d+)?)", "lt"),
    # Contains
    (r"(\w+)\s+(?:contains?|includes?|has)\s+[\"']?([^\"']+)[\"']?", "contains"),
    # In list
    (r"(\w+)\s+(?:in|one of)\s*\(([^)]+)\)", "in"),
    # Not/exclude
    (r"(?:not|exclude|without)\s+(\w+)\s*[=:]?\s*[\"']?([^\"']+)[\"']?", "neq"),
]

# Field name mappings
FIELD_ALIASES = {
    "type": "insight_type",
    "kind": "insight_type",
    "category": "category",
    "confidence": "confidence",
    "score": "confidence",
    "severity": "severity",
    "impact": "impact",
    "source": "document_id",
    "document": "document_id",
    "doc": "document_id",
}


class FilterExtractor:
    """Extract filters and constraints from queries."""

    def __init__(self):
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), operator)
            for pattern, operator in FILTER_PATTERNS
        ]

    def extract(self, query: str) -> list[QueryFilter]:
        """Extract filters from query.

        Args:
            query: The query text

        Returns:
            List of extracted filters
        """
        filters = []

        for pattern, operator in self._compiled_patterns:
            for match in pattern.finditer(query):
                field = self._normalize_field(match.group(1))
                value = self._parse_value(match.group(2), operator)

                filters.append(QueryFilter(
                    field=field,
                    operator=operator,
                    value=value,
                    negated=operator.startswith("n"),
                ))

        # Extract special filters
        filters.extend(self._extract_special_filters(query))

        logger.debug(
            "Filters extracted",
            query=query[:50],
            filter_count=len(filters),
        )

        return filters

    def _normalize_field(self, field: str) -> str:
        """Normalize field name using aliases."""
        field_lower = field.lower()
        return FIELD_ALIASES.get(field_lower, field_lower)

    def _parse_value(self, value: str, operator: str) -> Any:
        """Parse filter value to appropriate type."""
        value = value.strip().strip("\"'")

        if operator == "in":
            # Parse comma-separated list
            return [v.strip().strip("\"'") for v in value.split(",")]

        # Try numeric conversion
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Boolean conversion
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False

        return value

    def _extract_special_filters(self, query: str) -> list[QueryFilter]:
        """Extract special filter patterns."""
        filters = []
        query_lower = query.lower()

        # Confidence filters
        if "high confidence" in query_lower:
            filters.append(QueryFilter(field="confidence", operator="gte", value=0.8))
        elif "low confidence" in query_lower:
            filters.append(QueryFilter(field="confidence", operator="lte", value=0.5))

        # Type filters
        type_keywords = {
            "risks": ("insight_type", "eq", "risk"),
            "opportunities": ("insight_type", "eq", "opportunity"),
            "entities": ("insight_type", "eq", "entity"),
            "patterns": ("insight_type", "eq", "pattern"),
        }

        for keyword, (field, op, value) in type_keywords.items():
            if keyword in query_lower:
                filters.append(QueryFilter(field=field, operator=op, value=value))

        # Severity filters
        severity_keywords = {
            "critical": ("severity", "eq", "critical"),
            "high severity": ("severity", "in", ["critical", "high"]),
            "severe": ("severity", "in", ["critical", "high"]),
        }

        for keyword, (field, op, value) in severity_keywords.items():
            if keyword in query_lower:
                filters.append(QueryFilter(field=field, operator=op, value=value))

        return filters
