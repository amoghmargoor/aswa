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
