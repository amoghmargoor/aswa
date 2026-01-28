# Task 4.1.2: Natural Language Query Parser

## Context

You are working on the ASWA query-service at `/services/query-service/`. The service structure and API endpoints are implemented from Task 4.1.1.

Users submit natural language queries that need to be parsed and understood to:
1. Identify query intent (search, question, summary, comparison)
2. Extract entities, filters, and constraints
3. Determine time ranges and scope
4. Route to appropriate processing pipeline

## Objective

Create a natural language query parser that:
1. Classifies query intent
2. Extracts named entities and filters
3. Identifies temporal expressions
4. Normalizes and expands queries
5. Generates structured query representations

## Requirements

### 1. Create `/services/query-service/src/aswa_query/parser/__init__.py`
```python
from .query_parser import QueryParser, ParsedQuery
from .intent import IntentClassifier, QueryIntent
from .entities import EntityExtractor, ExtractedEntity
from .filters import FilterExtractor, QueryFilter
from .temporal import TemporalParser, TimeRange

__all__ = [
    "QueryParser",
    "ParsedQuery",
    "IntentClassifier",
    "QueryIntent",
    "EntityExtractor",
    "ExtractedEntity",
    "FilterExtractor",
    "QueryFilter",
    "TemporalParser",
    "TimeRange",
]
```

### 2. Create `/services/query-service/src/aswa_query/parser/models.py`
```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class QueryIntent(str, Enum):
    """Classified intent of a query."""
    FACTUAL = "factual"  # Looking for specific facts
    SUMMARY = "summary"  # Want a summary/overview
    COMPARISON = "comparison"  # Comparing entities/documents
    TREND = "trend"  # Looking for trends over time
    RISK = "risk"  # Risk-related queries
    OPPORTUNITY = "opportunity"  # Opportunity-related queries
    ENTITY = "entity"  # Entity-focused queries
    LIST = "list"  # Want a list of items
    EXPLANATION = "explanation"  # Want explanation/reasoning
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Types of extracted entities."""
    ORGANIZATION = "organization"
    PERSON = "person"
    LOCATION = "location"
    DATE = "date"
    MONEY = "money"
    PERCENTAGE = "percentage"
    PRODUCT = "product"
    DOCUMENT = "document"
    TOPIC = "topic"


@dataclass
class ExtractedEntity:
    """An entity extracted from the query."""
    text: str
    entity_type: EntityType
    confidence: float = 1.0
    normalized: str | None = None
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class TimeRange:
    """A temporal range extracted from the query."""
    start: datetime | None = None
    end: datetime | None = None
    relative: str | None = None  # "last 30 days", "this quarter"
    explicit: bool = False


@dataclass
class QueryFilter:
    """A filter/constraint extracted from the query."""
    field: str  # What field to filter on
    operator: str  # eq, gt, lt, contains, in
    value: Any
    negated: bool = False


@dataclass
class ParsedQuery:
    """A fully parsed query."""
    original_query: str
    normalized_query: str
    intent: QueryIntent
    confidence: float
    entities: list[ExtractedEntity] = field(default_factory=list)
    filters: list[QueryFilter] = field(default_factory=list)
    time_range: TimeRange | None = None
    keywords: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    document_scope: list[UUID] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_temporal_constraint(self) -> bool:
        return self.time_range is not None

    @property
    def entity_types(self) -> set[EntityType]:
        return {e.entity_type for e in self.entities}

    def get_entities_by_type(self, entity_type: EntityType) -> list[ExtractedEntity]:
        return [e for e in self.entities if e.entity_type == entity_type]
```

### 3. Create `/services/query-service/src/aswa_query/parser/intent.py`
```python
import re
from typing import Any
import structlog

from .models import QueryIntent

logger = structlog.get_logger()


# Intent patterns
INTENT_PATTERNS = {
    QueryIntent.SUMMARY: [
        r"\b(summarize|summary|overview|brief|highlight)\b",
        r"\bwhat (is|are) the (main|key|important)\b",
        r"\bgive me (a|an) (overview|summary)\b",
    ],
    QueryIntent.COMPARISON: [
        r"\b(compare|comparison|versus|vs\.?|differ|difference)\b",
        r"\bhow does .+ compare to\b",
        r"\bwhat('s| is) the difference between\b",
    ],
    QueryIntent.TREND: [
        r"\b(trend|trending|over time|growth|decline|change)\b",
        r"\bhow has .+ changed\b",
        r"\b(increase|decrease|rise|fall) in\b",
    ],
    QueryIntent.RISK: [
        r"\b(risk|danger|threat|concern|issue|problem|vulnerability)\b",
        r"\bwhat (could|might|may) go wrong\b",
        r"\bpotential (issues|problems)\b",
    ],
    QueryIntent.OPPORTUNITY: [
        r"\b(opportunity|opportunities|potential|growth|upside)\b",
        r"\bwhat (can|could) we (do|improve)\b",
        r"\bareas for (improvement|growth)\b",
    ],
    QueryIntent.ENTITY: [
        r"\bwho is\b",
        r"\bwhat (is|are) .+ (company|organization|person)\b",
        r"\btell me about\b",
    ],
    QueryIntent.LIST: [
        r"\b(list|enumerate|show me all|what are all)\b",
        r"\bhow many\b",
        r"\bgive me a list\b",
    ],
    QueryIntent.EXPLANATION: [
        r"\b(why|explain|how does|how do)\b",
        r"\bwhat causes\b",
        r"\breason for\b",
    ],
}


class IntentClassifier:
    """Classify query intent using patterns and heuristics."""

    def __init__(self):
        self._compiled_patterns: dict[QueryIntent, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns."""
        for intent, patterns in INTENT_PATTERNS.items():
            self._compiled_patterns[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify(self, query: str) -> tuple[QueryIntent, float]:
        """Classify query intent.

        Args:
            query: The query text

        Returns:
            Tuple of (intent, confidence)
        """
        query_lower = query.lower()
        scores: dict[QueryIntent, float] = {}

        # Pattern matching
        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    scores[intent] = scores.get(intent, 0) + 0.3

        # Keyword boosting
        scores = self._apply_keyword_boost(query_lower, scores)

        # Question word analysis
        scores = self._analyze_question_words(query_lower, scores)

        if not scores:
            return QueryIntent.FACTUAL, 0.5

        # Get highest scoring intent
        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent], 1.0)

        logger.debug(
            "Intent classified",
            query=query[:50],
            intent=best_intent,
            confidence=confidence,
        )

        return best_intent, confidence

    def _apply_keyword_boost(
        self,
        query: str,
        scores: dict[QueryIntent, float],
    ) -> dict[QueryIntent, float]:
        """Boost scores based on keywords."""
        keyword_boosts = {
            QueryIntent.RISK: ["risk", "threat", "danger", "problem", "concern"],
            QueryIntent.OPPORTUNITY: ["opportunity", "growth", "potential", "improve"],
            QueryIntent.SUMMARY: ["summary", "summarize", "overview", "brief"],
            QueryIntent.TREND: ["trend", "over time", "changed", "growth rate"],
        }

        for intent, keywords in keyword_boosts.items():
            for keyword in keywords:
                if keyword in query:
                    scores[intent] = scores.get(intent, 0) + 0.2

        return scores

    def _analyze_question_words(
        self,
        query: str,
        scores: dict[QueryIntent, float],
    ) -> dict[QueryIntent, float]:
        """Analyze question words for intent hints."""
        if query.startswith("who"):
            scores[QueryIntent.ENTITY] = scores.get(QueryIntent.ENTITY, 0) + 0.3
        elif query.startswith("why"):
            scores[QueryIntent.EXPLANATION] = scores.get(QueryIntent.EXPLANATION, 0) + 0.3
        elif query.startswith("how many"):
            scores[QueryIntent.LIST] = scores.get(QueryIntent.LIST, 0) + 0.3
        elif query.startswith("what are the"):
            scores[QueryIntent.LIST] = scores.get(QueryIntent.LIST, 0) + 0.2

        return scores

    def get_all_scores(self, query: str) -> dict[QueryIntent, float]:
        """Get scores for all intents."""
        query_lower = query.lower()
        scores: dict[QueryIntent, float] = {}

        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    scores[intent] = scores.get(intent, 0) + 0.3

        scores = self._apply_keyword_boost(query_lower, scores)
        scores = self._analyze_question_words(query_lower, scores)

        return scores
```

### 4. Create `/services/query-service/src/aswa_query/parser/entities.py`
```python
import re
from typing import Any
import structlog

from .models import ExtractedEntity, EntityType

logger = structlog.get_logger()


# Entity patterns
ENTITY_PATTERNS = {
    EntityType.MONEY: [
        r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|M|B|K))?",
        r"(?:USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?",
        r"[\d,]+(?:\.\d{2})?\s*(?:dollars|euros|pounds)",
    ],
    EntityType.PERCENTAGE: [
        r"\d+(?:\.\d+)?%",
        r"\d+(?:\.\d+)?\s*percent",
    ],
    EntityType.DATE: [
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\bQ[1-4]\s*\d{4}\b",
        r"\b(?:FY|fiscal year)\s*\d{4}\b",
    ],
}

# Common organization suffixes
ORG_SUFFIXES = [
    "Inc", "Corp", "Corporation", "LLC", "Ltd", "Company", "Co",
    "Group", "Holdings", "Partners", "Associates", "Industries",
]


class EntityExtractor:
    """Extract named entities from queries."""

    def __init__(self):
        self._compiled_patterns: dict[EntityType, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns."""
        for entity_type, patterns in ENTITY_PATTERNS.items():
            self._compiled_patterns[entity_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def extract(self, query: str) -> list[ExtractedEntity]:
        """Extract entities from query.

        Args:
            query: The query text

        Returns:
            List of extracted entities
        """
        entities = []

        # Pattern-based extraction
        for entity_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(query):
                    entities.append(ExtractedEntity(
                        text=match.group(),
                        entity_type=entity_type,
                        confidence=0.9,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    ))

        # Organization detection
        entities.extend(self._extract_organizations(query))

        # Remove overlapping entities (keep higher confidence)
        entities = self._remove_overlaps(entities)

        logger.debug(
            "Entities extracted",
            query=query[:50],
            entity_count=len(entities),
        )

        return entities

    def _extract_organizations(self, query: str) -> list[ExtractedEntity]:
        """Extract organization names."""
        entities = []

        # Look for capitalized words followed by org suffixes
        org_pattern = rf"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+({'|'.join(ORG_SUFFIXES)})\b"
        for match in re.finditer(org_pattern, query):
            entities.append(ExtractedEntity(
                text=match.group(),
                entity_type=EntityType.ORGANIZATION,
                confidence=0.85,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

        # Look for quoted company names
        quoted_pattern = r'"([^"]+)"'
        for match in re.finditer(quoted_pattern, query):
            entities.append(ExtractedEntity(
                text=match.group(1),
                entity_type=EntityType.ORGANIZATION,
                confidence=0.7,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

        return entities

    def _remove_overlaps(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Remove overlapping entities, keeping higher confidence ones."""
        if len(entities) <= 1:
            return entities

        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: (e.start_pos, -e.confidence))
        result = []
        last_end = -1

        for entity in sorted_entities:
            if entity.start_pos >= last_end:
                result.append(entity)
                last_end = entity.end_pos

        return result

    def normalize_entity(self, entity: ExtractedEntity) -> str:
        """Normalize entity text."""
        text = entity.text.strip()

        if entity.entity_type == EntityType.MONEY:
            # Normalize money amounts
            text = text.replace(",", "").replace("$", "").strip()
            if "million" in text.lower() or "M" in text:
                text = text.replace("million", "").replace("M", "").strip()
                try:
                    value = float(text) * 1_000_000
                    text = str(value)
                except ValueError:
                    pass

        elif entity.entity_type == EntityType.PERCENTAGE:
            text = text.replace("%", "").replace("percent", "").strip()

        return text
```

### 5. Create `/services/query-service/src/aswa_query/parser/temporal.py`
```python
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
```

### 6. Create `/services/query-service/src/aswa_query/parser/filters.py`
```python
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
```

### 7. Create `/services/query-service/src/aswa_query/parser/query_parser.py`
```python
import re
from typing import Any
from uuid import UUID
import hashlib
import structlog

from .models import ParsedQuery, QueryIntent, ExtractedEntity, QueryFilter, TimeRange
from .intent import IntentClassifier
from .entities import EntityExtractor
from .filters import FilterExtractor
from .temporal import TemporalParser

logger = structlog.get_logger()


# Stop words to remove during normalization
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "from", "up", "down", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "and", "but", "if", "or", "because", "as", "until", "while",
    "please", "tell", "me", "show", "give", "find", "get", "i", "want",
}


class QueryParser:
    """Parse natural language queries into structured representations."""

    def __init__(
        self,
        intent_classifier: IntentClassifier | None = None,
        entity_extractor: EntityExtractor | None = None,
        filter_extractor: FilterExtractor | None = None,
        temporal_parser: TemporalParser | None = None,
    ):
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.filter_extractor = filter_extractor or FilterExtractor()
        self.temporal_parser = temporal_parser or TemporalParser()

    def parse(
        self,
        query: str,
        document_scope: list[UUID] | None = None,
    ) -> ParsedQuery:
        """Parse a natural language query.

        Args:
            query: The query text
            document_scope: Optional document IDs to scope the query

        Returns:
            ParsedQuery with all extracted components
        """
        # Normalize query
        normalized = self._normalize_query(query)

        # Classify intent
        intent, confidence = self.intent_classifier.classify(query)

        # Extract entities
        entities = self.entity_extractor.extract(query)

        # Extract filters
        filters = self.filter_extractor.extract(query)

        # Parse temporal expressions
        time_range = self.temporal_parser.parse(query)

        # Extract keywords
        keywords = self._extract_keywords(normalized)

        # Expand terms (synonyms, related terms)
        expanded = self._expand_terms(keywords)

        parsed = ParsedQuery(
            original_query=query,
            normalized_query=normalized,
            intent=intent,
            confidence=confidence,
            entities=entities,
            filters=filters,
            time_range=time_range,
            keywords=keywords,
            expanded_terms=expanded,
            document_scope=document_scope,
        )

        logger.info(
            "Query parsed",
            intent=intent,
            confidence=confidence,
            entity_count=len(entities),
            filter_count=len(filters),
            has_temporal=time_range is not None,
        )

        return parsed

    def _normalize_query(self, query: str) -> str:
        """Normalize query text."""
        # Convert to lowercase
        normalized = query.lower().strip()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove punctuation except for meaningful ones
        normalized = re.sub(r"[^\w\s\-\.\?\$%]", "", normalized)

        return normalized

    def _extract_keywords(self, normalized_query: str) -> list[str]:
        """Extract meaningful keywords from query."""
        words = normalized_query.split()
        keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        return keywords

    def _expand_terms(self, keywords: list[str]) -> list[str]:
        """Expand keywords with synonyms and related terms."""
        # Synonym mappings
        synonyms = {
            "risk": ["threat", "danger", "concern", "issue"],
            "opportunity": ["potential", "upside", "growth"],
            "company": ["organization", "firm", "corporation", "business"],
            "increase": ["growth", "rise", "gain", "improvement"],
            "decrease": ["decline", "drop", "reduction", "fall"],
            "revenue": ["sales", "income", "earnings"],
            "profit": ["earnings", "income", "margin"],
            "cost": ["expense", "spending", "expenditure"],
        }

        expanded = []
        for keyword in keywords:
            if keyword in synonyms:
                expanded.extend(synonyms[keyword])

        return list(set(expanded))

    def get_query_hash(self, parsed: ParsedQuery) -> str:
        """Generate hash for query caching."""
        components = [
            parsed.normalized_query,
            parsed.intent.value,
            str(sorted([f.field for f in parsed.filters])),
            str(parsed.document_scope) if parsed.document_scope else "",
        ]
        content = ":".join(components)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_search_query(self, parsed: ParsedQuery) -> dict[str, Any]:
        """Convert parsed query to search parameters."""
        return {
            "query_text": parsed.normalized_query,
            "keywords": parsed.keywords + parsed.expanded_terms,
            "filters": [
                {"field": f.field, "operator": f.operator, "value": f.value}
                for f in parsed.filters
            ],
            "time_range": {
                "start": parsed.time_range.start.isoformat() if parsed.time_range and parsed.time_range.start else None,
                "end": parsed.time_range.end.isoformat() if parsed.time_range and parsed.time_range.end else None,
            } if parsed.time_range else None,
            "document_ids": [str(d) for d in parsed.document_scope] if parsed.document_scope else None,
        }
```

## Test Requirements

### Create `/services/query-service/tests/parser/__init__.py`

### Create `/services/query-service/tests/parser/test_intent.py`
```python
import pytest
from aswa_query.parser.intent import IntentClassifier
from aswa_query.parser.models import QueryIntent


class TestIntentClassifier:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_summary_intent(self, classifier):
        """Test summary intent detection."""
        queries = [
            "Give me a summary of the document",
            "Summarize the key points",
            "What are the main highlights?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.SUMMARY

    def test_risk_intent(self, classifier):
        """Test risk intent detection."""
        queries = [
            "What are the main risks?",
            "Show me potential threats",
            "What could go wrong?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.RISK

    def test_comparison_intent(self, classifier):
        """Test comparison intent detection."""
        queries = [
            "Compare company A and company B",
            "What's the difference between X and Y?",
            "How does this compare to last year?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.COMPARISON

    def test_trend_intent(self, classifier):
        """Test trend intent detection."""
        queries = [
            "What are the trends over time?",
            "How has revenue changed?",
            "Show me the growth pattern",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.TREND

    def test_factual_default(self, classifier):
        """Test factual is default for unclear queries."""
        intent, confidence = classifier.classify("What is the price?")
        assert intent in [QueryIntent.FACTUAL, QueryIntent.ENTITY]

    def test_confidence_score(self, classifier):
        """Test confidence scores are reasonable."""
        intent, confidence = classifier.classify("Summarize the risks")
        assert 0 <= confidence <= 1
```

### Create `/services/query-service/tests/parser/test_entities.py`
```python
import pytest
from aswa_query.parser.entities import EntityExtractor
from aswa_query.parser.models import EntityType


class TestEntityExtractor:
    @pytest.fixture
    def extractor(self):
        return EntityExtractor()

    def test_extract_money(self, extractor):
        """Test money entity extraction."""
        entities = extractor.extract("The revenue was $5 million")
        money_entities = [e for e in entities if e.entity_type == EntityType.MONEY]
        assert len(money_entities) >= 1

    def test_extract_percentage(self, extractor):
        """Test percentage extraction."""
        entities = extractor.extract("Growth was 15% year over year")
        pct_entities = [e for e in entities if e.entity_type == EntityType.PERCENTAGE]
        assert len(pct_entities) == 1
        assert "15%" in pct_entities[0].text

    def test_extract_date(self, extractor):
        """Test date extraction."""
        entities = extractor.extract("The meeting is on January 15, 2024")
        date_entities = [e for e in entities if e.entity_type == EntityType.DATE]
        assert len(date_entities) >= 1

    def test_extract_organization(self, extractor):
        """Test organization extraction."""
        entities = extractor.extract("Acme Corporation reported earnings")
        org_entities = [e for e in entities if e.entity_type == EntityType.ORGANIZATION]
        assert len(org_entities) >= 1

    def test_no_overlapping_entities(self, extractor):
        """Test overlapping entities are handled."""
        entities = extractor.extract("Acme Corp reported $50 million in Q1 2024")
        # Check no overlapping positions
        positions = [(e.start_pos, e.end_pos) for e in entities]
        for i, (start1, end1) in enumerate(positions):
            for j, (start2, end2) in enumerate(positions):
                if i != j:
                    assert not (start1 < end2 and end1 > start2)
```

### Create `/services/query-service/tests/parser/test_temporal.py`
```python
import pytest
from datetime import datetime, timedelta
from aswa_query.parser.temporal import TemporalParser


class TestTemporalParser:
    @pytest.fixture
    def parser(self):
        return TemporalParser()

    def test_last_n_days(self, parser):
        """Test 'last N days' parsing."""
        result = parser.parse("Show data from last 30 days")
        assert result is not None
        assert result.start is not None
        assert result.end is not None
        assert (result.end - result.start).days >= 29

    def test_this_month(self, parser):
        """Test 'this month' parsing."""
        result = parser.parse("What happened this month?")
        assert result is not None
        assert result.start.day == 1
        assert result.start.month == datetime.utcnow().month

    def test_last_quarter(self, parser):
        """Test 'last quarter' parsing."""
        result = parser.parse("Report for last quarter")
        assert result is not None
        assert result.relative == "last quarter"

    def test_explicit_quarter(self, parser):
        """Test explicit quarter parsing."""
        result = parser.parse("Show me Q1 2024 data")
        assert result is not None
        assert result.explicit is True
        assert result.start.year == 2024
        assert result.start.month == 1

    def test_ytd(self, parser):
        """Test year to date parsing."""
        result = parser.parse("Show YTD performance")
        assert result is not None
        assert result.start.month == 1
        assert result.start.day == 1

    def test_no_temporal(self, parser):
        """Test query with no temporal expression."""
        result = parser.parse("What are the main risks?")
        assert result is None
```

### Create `/services/query-service/tests/parser/test_query_parser.py`
```python
import pytest
from uuid import uuid4
from aswa_query.parser.query_parser import QueryParser
from aswa_query.parser.models import QueryIntent


class TestQueryParser:
    @pytest.fixture
    def parser(self):
        return QueryParser()

    def test_parse_simple_query(self, parser):
        """Test parsing a simple query."""
        result = parser.parse("What are the main risks?")
        assert result.original_query == "What are the main risks?"
        assert result.intent == QueryIntent.RISK
        assert len(result.keywords) > 0

    def test_parse_with_entities(self, parser):
        """Test parsing query with entities."""
        result = parser.parse("What is Acme Corp's revenue of $50 million?")
        assert len(result.entities) >= 1

    def test_parse_with_time(self, parser):
        """Test parsing query with temporal expression."""
        result = parser.parse("Show risks from last 30 days")
        assert result.time_range is not None
        assert result.has_temporal_constraint

    def test_parse_with_filters(self, parser):
        """Test parsing query with filters."""
        result = parser.parse("Show high confidence risks")
        assert len(result.filters) >= 1

    def test_parse_with_document_scope(self, parser):
        """Test parsing with document scope."""
        doc_ids = [uuid4(), uuid4()]
        result = parser.parse("Summarize the content", document_scope=doc_ids)
        assert result.document_scope == doc_ids

    def test_normalized_query(self, parser):
        """Test query normalization."""
        result = parser.parse("  What   ARE the   RISKS?  ")
        assert result.normalized_query == "what are the risks"

    def test_keyword_extraction(self, parser):
        """Test keyword extraction."""
        result = parser.parse("What are the financial risks for the company?")
        assert "financial" in result.keywords
        assert "risks" in result.keywords
        assert "company" in result.keywords
        # Stop words should be excluded
        assert "the" not in result.keywords
        assert "are" not in result.keywords

    def test_query_hash(self, parser):
        """Test query hash generation."""
        result1 = parser.parse("What are the risks?")
        result2 = parser.parse("What are the risks?")
        result3 = parser.parse("What are the opportunities?")

        hash1 = parser.get_query_hash(result1)
        hash2 = parser.get_query_hash(result2)
        hash3 = parser.get_query_hash(result3)

        assert hash1 == hash2  # Same query
        assert hash1 != hash3  # Different query

    def test_to_search_query(self, parser):
        """Test conversion to search query."""
        result = parser.parse("Show risks from last 30 days")
        search_query = parser.to_search_query(result)

        assert "query_text" in search_query
        assert "keywords" in search_query
        assert "filters" in search_query
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/parser/ -v`
2. Verify imports: `python -c "from aswa_query.parser import QueryParser, ParsedQuery"`
3. Test parsing: `python -c "from aswa_query.parser import QueryParser; p = QueryParser(); print(p.parse('What are the main risks?'))"`
