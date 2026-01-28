from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DigestPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DigestSection(str, Enum):
    SUMMARY = "summary"
    NEW_RISKS = "new_risks"
    NEW_OPPORTUNITIES = "new_opportunities"
    KEY_ENTITIES = "key_entities"
    TRENDS = "trends"
    DOCUMENT_ACTIVITY = "document_activity"


class DigestConfig(BaseModel):
    """Configuration for digest generation."""
    tenant_id: UUID
    period: DigestPeriod = DigestPeriod.DAILY
    sections: list[DigestSection] = Field(default_factory=lambda: [
        DigestSection.SUMMARY,
        DigestSection.NEW_RISKS,
        DigestSection.NEW_OPPORTUNITIES,
        DigestSection.TRENDS,
    ])
    max_items_per_section: int = 5
    min_confidence: float = 0.6
    include_low_priority: bool = False
    recipients: list[str] = Field(default_factory=list)
    delivery_hour: int = 9  # Hour of day to deliver
    timezone: str = "UTC"


class DigestItem(BaseModel):
    """An item in the digest."""
    id: UUID = Field(default_factory=uuid4)
    section: DigestSection
    title: str
    description: str
    importance: float = 0.5
    source_document: str | None = None
    source_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Digest(BaseModel):
    """A generated digest."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    period: DigestPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    title: str = ""
    summary: str = ""
    items: list[DigestItem] = Field(default_factory=list)

    # Statistics
    total_documents_processed: int = 0
    new_insights_count: int = 0
    high_priority_count: int = 0

    # Delivery tracking
    delivered: bool = False
    delivered_at: datetime | None = None
    delivery_channels: list[str] = Field(default_factory=list)

    def add_item(self, item: DigestItem) -> None:
        self.items.append(item)

    def get_items_by_section(self, section: DigestSection) -> list[DigestItem]:
        return [i for i in self.items if i.section == section]

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0
