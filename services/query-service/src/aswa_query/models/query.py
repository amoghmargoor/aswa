from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class QueryType(str, Enum):
    """Type of query."""
    SEARCH = "search"
    QUESTION = "question"
    SUMMARY = "summary"
    INSIGHTS = "insights"


class Citation(BaseModel):
    """A citation/source reference."""
    document_id: UUID
    document_name: str
    chunk_id: str | None = None
    page_number: int | None = None
    relevance_score: float
    excerpt: str = Field(..., max_length=500)


class QueryRequest(BaseModel):
    """Request to query the system."""
    query: str = Field(..., min_length=1, max_length=1000)
    query_type: QueryType = QueryType.QUESTION
    document_ids: list[UUID] | None = Field(None, description="Filter to specific documents")
    include_insights: bool = Field(True, description="Include extracted insights")
    include_raw_content: bool = Field(False, description="Include raw document content")
    max_results: int = Field(10, ge=1, le=50)
    min_relevance: float = Field(0.7, ge=0, le=1)

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        return v.strip()


class QueryResult(BaseModel):
    """A single query result."""
    id: UUID = Field(default_factory=uuid4)
    content: str
    content_type: str  # "insight", "document_chunk", "summary"
    relevance_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Response to a query."""
    query_id: UUID = Field(default_factory=uuid4)
    query: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    results: list[QueryResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    processing_time_ms: int
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchRequest(BaseModel):
    """Request for semantic search."""
    query: str = Field(..., min_length=1, max_length=500)
    document_ids: list[UUID] | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    min_score: float = Field(0.5, ge=0, le=1)


class SearchResult(BaseModel):
    """A search result."""
    document_id: UUID
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response to a search request."""
    query: str
    results: list[SearchResult]
    total_results: int
    processing_time_ms: int


class InsightQueryRequest(BaseModel):
    """Request to query insights."""
    query: str | None = Field(None, max_length=500)
    insight_types: list[str] | None = None
    document_ids: list[UUID] | None = None
    min_confidence: float = Field(0.5, ge=0, le=1)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
