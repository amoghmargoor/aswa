"""Entity extraction models."""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ExtractedInsightBase


class EntityType(str, Enum):
    """Types of entities that can be extracted."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    EVENT = "event"
    DATE = "date"
    MONEY = "money"
    PERCENTAGE = "percentage"
    REGULATION = "regulation"
    METRIC = "metric"
    OTHER = "other"


class EntityRelationshipType(str, Enum):
    """Types of relationships between entities."""

    WORKS_FOR = "works_for"
    OWNS = "owns"
    PARTNER_OF = "partner_of"
    COMPETITOR_OF = "competitor_of"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    MANAGES = "manages"
    RELATED_TO = "related_to"


class ExtractedEntity(ExtractedInsightBase):
    """An entity extracted from text."""

    name: str = Field(..., min_length=1, max_length=500, description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    description: str = Field(..., max_length=2000, description="Brief description")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Key attributes"
    )


class EntityRelationship(BaseModel):
    """A relationship between two entities."""

    source_entity: str = Field(..., description="Name of source entity")
    target_entity: str = Field(..., description="Name of target entity")
    relationship_type: EntityRelationshipType
    description: str = Field(..., description="Description of relationship")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    bidirectional: bool = Field(False, description="If relationship goes both ways")


class EntityExtractionResult(BaseModel):
    """Result of entity extraction from a document."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
