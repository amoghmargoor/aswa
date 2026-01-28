"""Base models and common types for insight extraction."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceLevel(str, Enum):
    """Confidence level categories."""

    VERY_LOW = "very_low"  # 0.0 - 0.2
    LOW = "low"  # 0.2 - 0.4
    MEDIUM = "medium"  # 0.4 - 0.6
    HIGH = "high"  # 0.6 - 0.8
    VERY_HIGH = "very_high"  # 0.8 - 1.0


class SourceReference(BaseModel):
    """Reference to source text."""

    text: str = Field(..., description="The exact quoted text from the source")
    page: int | None = Field(None, description="Page number if applicable")
    section: str | None = Field(None, description="Section name if applicable")
    start_offset: int | None = Field(
        None, description="Character offset in document"
    )
    end_offset: int | None = Field(None, description="End character offset")


class ExtractedInsightBase(BaseModel):
    """Base class for all extracted insights."""

    model_config = ConfigDict(use_enum_values=True)

    confidence: Annotated[
        float, Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    ]
    sources: list[SourceReference] = Field(
        default_factory=list, description="Source references"
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get categorical confidence level."""
        if self.confidence < 0.2:
            return ConfidenceLevel.VERY_LOW
        elif self.confidence < 0.4:
            return ConfidenceLevel.LOW
        elif self.confidence < 0.6:
            return ConfidenceLevel.MEDIUM
        elif self.confidence < 0.8:
            return ConfidenceLevel.HIGH
        else:
            return ConfidenceLevel.VERY_HIGH
