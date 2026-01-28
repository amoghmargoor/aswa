from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ContentType(str, Enum):
    """Type of retrieved content."""
    DOCUMENT_CHUNK = "document_chunk"
    INSIGHT = "insight"
    ENTITY = "entity"
    SUMMARY = "summary"


@dataclass
class SearchResult:
    """A single search result."""
    id: str
    content: str
    content_type: ContentType
    score: float
    document_id: UUID | None = None
    document_name: str | None = None
    chunk_index: int | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_reference(self) -> str:
        """Generate source reference string."""
        if self.document_name:
            ref = self.document_name
            if self.page_number:
                ref += f", p.{self.page_number}"
            return ref
        return self.id


@dataclass
class InsightResult:
    """A retrieved insight."""
    id: UUID
    title: str
    description: str
    insight_type: str
    confidence: float
    score: float
    document_id: UUID | None = None
    document_name: str | None = None
    category: str | None = None
    severity: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Combined retrieval results."""
    query: str
    document_chunks: list[SearchResult] = field(default_factory=list)
    insights: list[InsightResult] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    total_chunks: int = 0
    total_insights: int = 0
    retrieval_time_ms: int = 0

    @property
    def has_results(self) -> bool:
        return bool(self.document_chunks or self.insights)

    @property
    def top_documents(self) -> set[UUID]:
        """Get unique document IDs from top results."""
        doc_ids = set()
        for chunk in self.document_chunks:
            if chunk.document_id:
                doc_ids.add(chunk.document_id)
        return doc_ids


@dataclass
class ContextWindow:
    """A context window for LLM generation."""
    content: str
    token_count: int
    sources: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
