# Task 4.2.1: Context Retrieval Pipeline

## Context

You are working on the ASWA query-service at `/services/query-service/`. The service structure (Task 4.1.1) and query parser (Task 4.1.2) are implemented.

The context retrieval pipeline is the core RAG component that:
1. Retrieves relevant document chunks from the vector store
2. Fetches related insights from the insight-engine
3. Ranks and filters results by relevance
4. Builds context for answer generation

## Objective

Create a context retrieval pipeline that:
1. Performs semantic search against Qdrant vector store
2. Retrieves relevant insights from insight-engine
3. Combines and ranks results using hybrid scoring
4. Filters by tenant, document scope, and time range
5. Returns structured context for LLM generation

## Requirements

### 1. Create `/services/query-service/src/aswa_query/retrieval/__init__.py`
```python
from .pipeline import RetrievalPipeline, RetrievalResult
from .vector_search import VectorSearcher, SearchResult
from .insight_retriever import InsightRetriever
from .reranker import Reranker, RerankerConfig
from .context_builder import ContextBuilder, ContextWindow

__all__ = [
    "RetrievalPipeline",
    "RetrievalResult",
    "VectorSearcher",
    "SearchResult",
    "InsightRetriever",
    "Reranker",
    "RerankerConfig",
    "ContextBuilder",
    "ContextWindow",
]
```

### 2. Create `/services/query-service/src/aswa_query/retrieval/models.py`
```python
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
```

### 3. Create `/services/query-service/src/aswa_query/retrieval/vector_search.py`
```python
from typing import Any
from uuid import UUID
import structlog

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from aswa_query.config import Settings
from .models import SearchResult, ContentType

logger = structlog.get_logger()


class VectorSearcher:
    """Search documents using vector similarity."""

    def __init__(
        self,
        settings: Settings,
        embedding_client: Any | None = None,
    ):
        self.settings = settings
        self.embedding_client = embedding_client
        self._qdrant_client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.settings.qdrant_url)
        return self._qdrant_client

    async def search(
        self,
        query: str,
        tenant_id: UUID,
        document_ids: list[UUID] | None = None,
        limit: int = 10,
        min_score: float = 0.5,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Perform semantic search.

        Args:
            query: Search query text
            tenant_id: Tenant ID for isolation
            document_ids: Optional document scope
            limit: Maximum results
            min_score: Minimum similarity score
            offset: Result offset

        Returns:
            List of search results
        """
        # Generate query embedding
        query_embedding = await self._embed_query(query)

        # Build filter
        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]

        if document_ids:
            filter_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=[str(d) for d in document_ids]),
                )
            )

        # Execute search
        client = self._get_client()
        try:
            results = client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=query_embedding,
                query_filter=Filter(must=filter_conditions),
                limit=limit,
                offset=offset,
                score_threshold=min_score,
                with_payload=True,
            )

            search_results = []
            for result in results:
                payload = result.payload or {}
                search_results.append(SearchResult(
                    id=str(result.id),
                    content=payload.get("content", ""),
                    content_type=ContentType.DOCUMENT_CHUNK,
                    score=result.score,
                    document_id=UUID(payload["document_id"]) if payload.get("document_id") else None,
                    document_name=payload.get("document_name"),
                    chunk_index=payload.get("chunk_index"),
                    page_number=payload.get("page_number"),
                    metadata=payload.get("metadata", {}),
                ))

            logger.info(
                "Vector search completed",
                query_length=len(query),
                result_count=len(search_results),
            )

            return search_results

        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            raise

    async def search_by_vector(
        self,
        vector: list[float],
        tenant_id: UUID,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[SearchResult]:
        """Search using a pre-computed vector."""
        client = self._get_client()

        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]

        results = client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=vector,
            query_filter=Filter(must=filter_conditions),
            limit=limit,
            score_threshold=min_score,
            with_payload=True,
        )

        return [
            SearchResult(
                id=str(r.id),
                content=r.payload.get("content", "") if r.payload else "",
                content_type=ContentType.DOCUMENT_CHUNK,
                score=r.score,
                document_id=UUID(r.payload["document_id"]) if r.payload and r.payload.get("document_id") else None,
                document_name=r.payload.get("document_name") if r.payload else None,
                metadata=r.payload.get("metadata", {}) if r.payload else {},
            )
            for r in results
        ]

    async def find_similar_chunks(
        self,
        chunk_id: str,
        tenant_id: UUID,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Find chunks similar to a given chunk."""
        client = self._get_client()

        # Get the original chunk's vector
        points = client.retrieve(
            collection_name=self.settings.qdrant_collection,
            ids=[chunk_id],
            with_vectors=True,
        )

        if not points:
            return []

        vector = points[0].vector
        if isinstance(vector, dict):
            vector = list(vector.values())[0]

        return await self.search_by_vector(
            vector=vector,
            tenant_id=tenant_id,
            limit=limit + 1,  # Exclude self
        )[1:]  # Skip first (self)

    async def _embed_query(self, query: str) -> list[float]:
        """Generate embedding for query."""
        if self.embedding_client:
            return await self.embedding_client.embed(query)

        # Fallback: use a simple embedding service
        # In production, this should use the same embedding model as indexing
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.qdrant_url.replace('6333', '8080')}/embed",
                json={"text": query},
                timeout=30.0,
            )
            if response.status_code == 200:
                return response.json()["embedding"]

        raise ValueError("No embedding client available")

    async def get_document_chunks(
        self,
        document_id: UUID,
        tenant_id: UUID,
    ) -> list[SearchResult]:
        """Get all chunks for a document."""
        client = self._get_client()

        results = client.scroll(
            collection_name=self.settings.qdrant_collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                    FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
                ]
            ),
            with_payload=True,
            limit=1000,
        )

        chunks = []
        for point in results[0]:
            payload = point.payload or {}
            chunks.append(SearchResult(
                id=str(point.id),
                content=payload.get("content", ""),
                content_type=ContentType.DOCUMENT_CHUNK,
                score=1.0,
                document_id=document_id,
                document_name=payload.get("document_name"),
                chunk_index=payload.get("chunk_index"),
                page_number=payload.get("page_number"),
                metadata=payload.get("metadata", {}),
            ))

        # Sort by chunk index
        chunks.sort(key=lambda c: c.chunk_index or 0)
        return chunks
```

### 4. Create `/services/query-service/src/aswa_query/retrieval/insight_retriever.py`
```python
from typing import Any
from uuid import UUID
import httpx
import structlog

from aswa_query.config import Settings
from aswa_query.parser.models import ParsedQuery, QueryIntent
from .models import InsightResult

logger = structlog.get_logger()


class InsightRetriever:
    """Retrieve insights from insight-engine."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.insight_engine_url.rstrip("/")

    async def retrieve(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[InsightResult]:
        """Retrieve relevant insights based on query.

        Args:
            query: Parsed query
            tenant_id: Tenant ID
            limit: Maximum results

        Returns:
            List of insight results
        """
        # Determine insight types based on query intent
        insight_types = self._get_insight_types(query.intent)

        # Build request
        request_body = {
            "query": query.normalized_query,
            "insight_types": insight_types,
            "min_confidence": 0.5,
            "limit": limit,
        }

        # Add document scope if present
        if query.document_scope:
            request_body["document_ids"] = [str(d) for d in query.document_scope]

        # Add time range if present
        if query.time_range:
            if query.time_range.start:
                request_body["start_date"] = query.time_range.start.isoformat()
            if query.time_range.end:
                request_body["end_date"] = query.time_range.end.isoformat()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/insights/search",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    json=request_body,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                insights = []
                for item in data.get("items", []):
                    insights.append(InsightResult(
                        id=UUID(item["id"]),
                        title=item["title"],
                        description=item["description"],
                        insight_type=item["insight_type"],
                        confidence=item.get("confidence", 0.5),
                        score=item.get("score", 0.5),
                        document_id=UUID(item["document_id"]) if item.get("document_id") else None,
                        document_name=item.get("document_name"),
                        category=item.get("category"),
                        severity=item.get("severity"),
                        metadata=item.get("metadata", {}),
                    ))

                logger.info(
                    "Insights retrieved",
                    count=len(insights),
                    types=insight_types,
                )

                return insights

        except httpx.HTTPError as e:
            logger.error("Insight retrieval failed", error=str(e))
            return []

    async def get_insight_by_id(
        self,
        insight_id: UUID,
        tenant_id: UUID,
    ) -> InsightResult | None:
        """Get a specific insight by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/insights/{insight_id}",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    timeout=10.0,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                item = response.json()

                return InsightResult(
                    id=UUID(item["id"]),
                    title=item["title"],
                    description=item["description"],
                    insight_type=item["insight_type"],
                    confidence=item.get("confidence", 0.5),
                    score=1.0,
                    document_id=UUID(item["document_id"]) if item.get("document_id") else None,
                    category=item.get("category"),
                    severity=item.get("severity"),
                    metadata=item.get("metadata", {}),
                )

        except httpx.HTTPError as e:
            logger.error("Insight fetch failed", insight_id=str(insight_id), error=str(e))
            return None

    async def get_related_insights(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        limit: int = 5,
    ) -> list[InsightResult]:
        """Get insights related to a given insight."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/insights/{insight_id}/related",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    params={"limit": limit},
                    timeout=10.0,
                )
                response.raise_for_status()

                return [
                    InsightResult(
                        id=UUID(item["id"]),
                        title=item["title"],
                        description=item["description"],
                        insight_type=item["insight_type"],
                        confidence=item.get("confidence", 0.5),
                        score=item.get("score", 0.5),
                    )
                    for item in response.json().get("items", [])
                ]

        except httpx.HTTPError as e:
            logger.error("Related insights fetch failed", error=str(e))
            return []

    def _get_insight_types(self, intent: QueryIntent) -> list[str] | None:
        """Map query intent to insight types."""
        intent_type_map = {
            QueryIntent.RISK: ["risk"],
            QueryIntent.OPPORTUNITY: ["opportunity"],
            QueryIntent.ENTITY: ["entity"],
            QueryIntent.TREND: ["pattern", "trend"],
        }
        return intent_type_map.get(intent)
```

### 5. Create `/services/query-service/src/aswa_query/retrieval/reranker.py`
```python
from dataclasses import dataclass, field
from typing import Any
import structlog

from .models import SearchResult, InsightResult

logger = structlog.get_logger()


@dataclass
class RerankerConfig:
    """Configuration for reranking."""
    chunk_weight: float = 0.6
    insight_weight: float = 0.4
    recency_boost: float = 0.1
    confidence_weight: float = 0.2
    keyword_boost: float = 0.15
    diversity_penalty: float = 0.1


class Reranker:
    """Rerank and combine search results."""

    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()

    def rerank_chunks(
        self,
        results: list[SearchResult],
        query_keywords: list[str],
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Rerank document chunks.

        Args:
            results: Search results to rerank
            query_keywords: Keywords from parsed query
            max_results: Maximum results to return

        Returns:
            Reranked results
        """
        if not results:
            return []

        scored_results = []
        seen_content_hashes = set()

        for result in results:
            # Calculate combined score
            score = result.score

            # Keyword boost
            content_lower = result.content.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw.lower() in content_lower)
            if query_keywords:
                score += self.config.keyword_boost * (keyword_matches / len(query_keywords))

            # Diversity penalty (penalize similar content)
            content_hash = hash(result.content[:100])
            if content_hash in seen_content_hashes:
                score *= (1 - self.config.diversity_penalty)
            else:
                seen_content_hashes.add(content_hash)

            scored_results.append((score, result))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Return top results with updated scores
        reranked = []
        for score, result in scored_results[:max_results]:
            result.score = score
            reranked.append(result)

        return reranked

    def rerank_insights(
        self,
        insights: list[InsightResult],
        query_keywords: list[str],
        max_results: int = 10,
    ) -> list[InsightResult]:
        """Rerank insights.

        Args:
            insights: Insights to rerank
            query_keywords: Keywords from parsed query
            max_results: Maximum results to return

        Returns:
            Reranked insights
        """
        if not insights:
            return []

        scored_insights = []

        for insight in insights:
            # Base score
            score = insight.score

            # Confidence weight
            score += self.config.confidence_weight * insight.confidence

            # Keyword boost
            text = f"{insight.title} {insight.description}".lower()
            keyword_matches = sum(1 for kw in query_keywords if kw.lower() in text)
            if query_keywords:
                score += self.config.keyword_boost * (keyword_matches / len(query_keywords))

            scored_insights.append((score, insight))

        # Sort by score
        scored_insights.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for score, insight in scored_insights[:max_results]:
            insight.score = score
            reranked.append(insight)

        return reranked

    def combine_results(
        self,
        chunks: list[SearchResult],
        insights: list[InsightResult],
        max_total: int = 15,
    ) -> tuple[list[SearchResult], list[InsightResult]]:
        """Combine and balance chunk and insight results.

        Args:
            chunks: Document chunks
            insights: Insights
            max_total: Maximum total results

        Returns:
            Tuple of (chunks, insights) with balanced counts
        """
        # Calculate target counts based on weights
        chunk_target = int(max_total * self.config.chunk_weight)
        insight_target = max_total - chunk_target

        # Adjust if one category has fewer results
        if len(chunks) < chunk_target:
            insight_target = min(len(insights), max_total - len(chunks))
            chunk_target = len(chunks)
        elif len(insights) < insight_target:
            chunk_target = min(len(chunks), max_total - len(insights))
            insight_target = len(insights)

        return chunks[:chunk_target], insights[:insight_target]

    def deduplicate_results(
        self,
        results: list[SearchResult],
        similarity_threshold: float = 0.9,
    ) -> list[SearchResult]:
        """Remove near-duplicate results.

        Args:
            results: Results to deduplicate
            similarity_threshold: Jaccard similarity threshold

        Returns:
            Deduplicated results
        """
        if len(results) <= 1:
            return results

        unique_results = []
        seen_contents = []

        for result in results:
            content_words = set(result.content.lower().split())
            is_duplicate = False

            for seen_words in seen_contents:
                if not content_words or not seen_words:
                    continue

                intersection = len(content_words & seen_words)
                union = len(content_words | seen_words)
                similarity = intersection / union if union > 0 else 0

                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_results.append(result)
                seen_contents.append(content_words)

        return unique_results
```

### 6. Create `/services/query-service/src/aswa_query/retrieval/context_builder.py`
```python
from typing import Any
import tiktoken
import structlog

from .models import SearchResult, InsightResult, ContextWindow, RetrievalResult

logger = structlog.get_logger()


class ContextBuilder:
    """Build context windows for LLM generation."""

    def __init__(
        self,
        max_tokens: int = 4000,
        model: str = "gpt-4",
    ):
        self.max_tokens = max_tokens
        self.model = model
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def build_context(
        self,
        retrieval_result: RetrievalResult,
        include_insights: bool = True,
        include_chunks: bool = True,
    ) -> ContextWindow:
        """Build context window from retrieval results.

        Args:
            retrieval_result: Results from retrieval pipeline
            include_insights: Include insights in context
            include_chunks: Include document chunks in context

        Returns:
            ContextWindow with formatted content
        """
        sections = []
        sources = []
        total_tokens = 0

        # Add document chunks
        if include_chunks and retrieval_result.document_chunks:
            chunk_section, chunk_sources, chunk_tokens = self._format_chunks(
                retrieval_result.document_chunks,
                self.max_tokens - total_tokens,
            )
            if chunk_section:
                sections.append(chunk_section)
                sources.extend(chunk_sources)
                total_tokens += chunk_tokens

        # Add insights
        if include_insights and retrieval_result.insights:
            insight_section, insight_sources, insight_tokens = self._format_insights(
                retrieval_result.insights,
                self.max_tokens - total_tokens,
            )
            if insight_section:
                sections.append(insight_section)
                sources.extend(insight_sources)
                total_tokens += insight_tokens

        content = "\n\n".join(sections)

        return ContextWindow(
            content=content,
            token_count=total_tokens,
            sources=sources,
            metadata={
                "chunk_count": len(retrieval_result.document_chunks),
                "insight_count": len(retrieval_result.insights),
            },
        )

    def _format_chunks(
        self,
        chunks: list[SearchResult],
        max_tokens: int,
    ) -> tuple[str, list[str], int]:
        """Format document chunks for context."""
        if not chunks:
            return "", [], 0

        lines = ["## Relevant Document Excerpts\n"]
        sources = []
        tokens_used = self._count_tokens(lines[0])

        for i, chunk in enumerate(chunks, 1):
            # Format chunk
            source_ref = chunk.source_reference
            chunk_text = f"### [{i}] {source_ref}\n{chunk.content}\n"

            chunk_tokens = self._count_tokens(chunk_text)
            if tokens_used + chunk_tokens > max_tokens:
                break

            lines.append(chunk_text)
            sources.append(source_ref)
            tokens_used += chunk_tokens

        return "\n".join(lines), sources, tokens_used

    def _format_insights(
        self,
        insights: list[InsightResult],
        max_tokens: int,
    ) -> tuple[str, list[str], int]:
        """Format insights for context."""
        if not insights:
            return "", [], 0

        lines = ["## Extracted Insights\n"]
        sources = []
        tokens_used = self._count_tokens(lines[0])

        for insight in insights:
            # Format insight
            insight_text = f"### {insight.insight_type.upper()}: {insight.title}\n"
            insight_text += f"{insight.description}\n"

            if insight.severity:
                insight_text += f"Severity: {insight.severity}\n"
            if insight.category:
                insight_text += f"Category: {insight.category}\n"

            insight_text += f"Confidence: {insight.confidence:.0%}\n"

            insight_tokens = self._count_tokens(insight_text)
            if tokens_used + insight_tokens > max_tokens:
                break

            lines.append(insight_text)
            if insight.document_name:
                sources.append(insight.document_name)
            tokens_used += insight_tokens

        return "\n".join(lines), sources, tokens_used

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def build_summary_context(
        self,
        retrieval_result: RetrievalResult,
    ) -> ContextWindow:
        """Build condensed context for summary generation."""
        # For summaries, prioritize insights over raw chunks
        sections = []
        sources = []
        total_tokens = 0

        # Add insight summary
        if retrieval_result.insights:
            insight_types = {}
            for insight in retrieval_result.insights:
                itype = insight.insight_type
                if itype not in insight_types:
                    insight_types[itype] = []
                insight_types[itype].append(insight)

            summary_lines = ["## Key Insights Summary\n"]
            for itype, insights in insight_types.items():
                summary_lines.append(f"### {itype.title()} ({len(insights)})")
                for insight in insights[:3]:  # Top 3 per type
                    summary_lines.append(f"- {insight.title}")
                    if insight.document_name:
                        sources.append(insight.document_name)

            section = "\n".join(summary_lines)
            sections.append(section)
            total_tokens += self._count_tokens(section)

        # Add abbreviated chunks
        if retrieval_result.document_chunks and total_tokens < self.max_tokens - 500:
            chunk_lines = ["## Key Document Points\n"]
            for chunk in retrieval_result.document_chunks[:5]:
                # Take first 200 chars of each chunk
                abbreviated = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
                chunk_lines.append(f"- {abbreviated}")
                if chunk.source_reference:
                    sources.append(chunk.source_reference)

            section = "\n".join(chunk_lines)
            sections.append(section)
            total_tokens += self._count_tokens(section)

        return ContextWindow(
            content="\n\n".join(sections),
            token_count=total_tokens,
            sources=list(set(sources)),
        )
```

### 7. Create `/services/query-service/src/aswa_query/retrieval/pipeline.py`
```python
import asyncio
import time
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from aswa_query.parser.models import ParsedQuery
from .models import RetrievalResult, SearchResult, InsightResult, ContextWindow
from .vector_search import VectorSearcher
from .insight_retriever import InsightRetriever
from .reranker import Reranker, RerankerConfig
from .context_builder import ContextBuilder

logger = structlog.get_logger()


class RetrievalPipeline:
    """Main retrieval pipeline for RAG."""

    def __init__(
        self,
        settings: Settings,
        vector_searcher: VectorSearcher | None = None,
        insight_retriever: InsightRetriever | None = None,
        reranker: Reranker | None = None,
        context_builder: ContextBuilder | None = None,
    ):
        self.settings = settings
        self.vector_searcher = vector_searcher or VectorSearcher(settings)
        self.insight_retriever = insight_retriever or InsightRetriever(settings)
        self.reranker = reranker or Reranker()
        self.context_builder = context_builder or ContextBuilder(
            max_tokens=settings.llm_max_tokens - 1000  # Reserve tokens for generation
        )

    async def retrieve(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        include_chunks: bool = True,
        include_insights: bool = True,
        max_chunks: int = 10,
        max_insights: int = 10,
    ) -> RetrievalResult:
        """Execute retrieval pipeline.

        Args:
            query: Parsed query
            tenant_id: Tenant ID
            include_chunks: Include document chunks
            include_insights: Include insights
            max_chunks: Maximum chunks to retrieve
            max_insights: Maximum insights to retrieve

        Returns:
            RetrievalResult with all retrieved content
        """
        start_time = time.time()

        # Run retrievals in parallel
        tasks = []

        if include_chunks:
            tasks.append(self._retrieve_chunks(query, tenant_id, max_chunks))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

        if include_insights:
            tasks.append(self._retrieve_insights(query, tenant_id, max_insights))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

        chunks, insights = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        if isinstance(chunks, Exception):
            logger.error("Chunk retrieval failed", error=str(chunks))
            chunks = []
        if isinstance(insights, Exception):
            logger.error("Insight retrieval failed", error=str(insights))
            insights = []

        # Rerank results
        chunks = self.reranker.rerank_chunks(chunks, query.keywords, max_chunks)
        chunks = self.reranker.deduplicate_results(chunks)

        insights = self.reranker.rerank_insights(insights, query.keywords, max_insights)

        # Balance results
        chunks, insights = self.reranker.combine_results(
            chunks, insights, max_chunks + max_insights
        )

        retrieval_time = int((time.time() - start_time) * 1000)

        result = RetrievalResult(
            query=query.original_query,
            document_chunks=chunks,
            insights=insights,
            total_chunks=len(chunks),
            total_insights=len(insights),
            retrieval_time_ms=retrieval_time,
        )

        logger.info(
            "Retrieval completed",
            chunks=len(chunks),
            insights=len(insights),
            time_ms=retrieval_time,
        )

        return result

    async def retrieve_and_build_context(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        **kwargs,
    ) -> tuple[RetrievalResult, ContextWindow]:
        """Retrieve content and build context window.

        Args:
            query: Parsed query
            tenant_id: Tenant ID
            **kwargs: Additional retrieval arguments

        Returns:
            Tuple of (RetrievalResult, ContextWindow)
        """
        result = await self.retrieve(query, tenant_id, **kwargs)
        context = self.context_builder.build_context(result)
        return result, context

    async def _retrieve_chunks(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        limit: int,
    ) -> list[SearchResult]:
        """Retrieve document chunks."""
        return await self.vector_searcher.search(
            query=query.normalized_query,
            tenant_id=tenant_id,
            document_ids=query.document_scope,
            limit=limit,
            min_score=self.settings.min_relevance_score,
        )

    async def _retrieve_insights(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        limit: int,
    ) -> list[InsightResult]:
        """Retrieve insights."""
        return await self.insight_retriever.retrieve(
            query=query,
            tenant_id=tenant_id,
            limit=limit,
        )

    async def retrieve_for_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
    ) -> RetrievalResult:
        """Retrieve all content for a specific document."""
        # Get all chunks for document
        chunks = await self.vector_searcher.get_document_chunks(document_id, tenant_id)

        # Get insights for document
        # (would need document-scoped insight query)

        return RetrievalResult(
            query=f"document:{document_id}",
            document_chunks=chunks,
            insights=[],
            total_chunks=len(chunks),
        )
```

## Test Requirements

### Create `/services/query-service/tests/retrieval/__init__.py`

### Create `/services/query-service/tests/retrieval/test_vector_search.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from aswa_query.retrieval.vector_search import VectorSearcher
from aswa_query.config import Settings


class TestVectorSearcher:
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def searcher(self, settings):
        return VectorSearcher(settings)

    @pytest.mark.asyncio
    async def test_search_builds_filter(self, searcher):
        """Test that search builds correct filter."""
        tenant_id = uuid4()
        doc_ids = [uuid4(), uuid4()]

        with patch.object(searcher, '_get_client') as mock_client:
            mock_qdrant = MagicMock()
            mock_qdrant.search.return_value = []
            mock_client.return_value = mock_qdrant

            with patch.object(searcher, '_embed_query', new_callable=AsyncMock) as mock_embed:
                mock_embed.return_value = [0.1] * 384

                await searcher.search(
                    query="test query",
                    tenant_id=tenant_id,
                    document_ids=doc_ids,
                )

                mock_qdrant.search.assert_called_once()
                call_kwargs = mock_qdrant.search.call_args.kwargs
                assert 'query_filter' in call_kwargs

    @pytest.mark.asyncio
    async def test_search_returns_results(self, searcher):
        """Test search result formatting."""
        # This would require mocking Qdrant responses
        pass
```

### Create `/services/query-service/tests/retrieval/test_reranker.py`
```python
import pytest
from uuid import uuid4

from aswa_query.retrieval.reranker import Reranker, RerankerConfig
from aswa_query.retrieval.models import SearchResult, InsightResult, ContentType


class TestReranker:
    @pytest.fixture
    def reranker(self):
        return Reranker()

    def test_rerank_chunks_by_keywords(self, reranker):
        """Test keyword boosting in reranking."""
        chunks = [
            SearchResult(id="1", content="This is about risk management", content_type=ContentType.DOCUMENT_CHUNK, score=0.8),
            SearchResult(id="2", content="This is about something else", content_type=ContentType.DOCUMENT_CHUNK, score=0.85),
        ]

        reranked = reranker.rerank_chunks(chunks, ["risk", "management"])

        # First result should be boosted due to keyword matches
        assert reranked[0].id == "1"

    def test_rerank_insights_by_confidence(self, reranker):
        """Test confidence weighting in insight reranking."""
        insights = [
            InsightResult(id=uuid4(), title="Low confidence", description="desc", insight_type="risk", confidence=0.5, score=0.8),
            InsightResult(id=uuid4(), title="High confidence", description="desc", insight_type="risk", confidence=0.95, score=0.75),
        ]

        reranked = reranker.rerank_insights(insights, [])

        # High confidence should be ranked higher despite lower base score
        assert reranked[0].confidence == 0.95

    def test_combine_results_balancing(self, reranker):
        """Test result balancing."""
        chunks = [SearchResult(id=str(i), content=f"chunk {i}", content_type=ContentType.DOCUMENT_CHUNK, score=0.9) for i in range(10)]
        insights = [InsightResult(id=uuid4(), title=f"insight {i}", description="", insight_type="risk", confidence=0.8, score=0.8) for i in range(5)]

        combined_chunks, combined_insights = reranker.combine_results(chunks, insights, max_total=10)

        assert len(combined_chunks) + len(combined_insights) <= 10
        assert len(combined_chunks) > 0
        assert len(combined_insights) > 0

    def test_deduplicate_results(self, reranker):
        """Test deduplication."""
        chunks = [
            SearchResult(id="1", content="This is the same content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9),
            SearchResult(id="2", content="This is the same content", content_type=ContentType.DOCUMENT_CHUNK, score=0.8),
            SearchResult(id="3", content="This is different content", content_type=ContentType.DOCUMENT_CHUNK, score=0.7),
        ]

        deduplicated = reranker.deduplicate_results(chunks)

        assert len(deduplicated) == 2
```

### Create `/services/query-service/tests/retrieval/test_pipeline.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_query.retrieval.pipeline import RetrievalPipeline
from aswa_query.retrieval.models import SearchResult, InsightResult, ContentType
from aswa_query.parser.models import ParsedQuery, QueryIntent
from aswa_query.config import Settings


class TestRetrievalPipeline:
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def mock_vector_searcher(self):
        searcher = MagicMock()
        searcher.search = AsyncMock(return_value=[
            SearchResult(id="1", content="Test content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4()),
        ])
        return searcher

    @pytest.fixture
    def mock_insight_retriever(self):
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(return_value=[
            InsightResult(id=uuid4(), title="Test insight", description="desc", insight_type="risk", confidence=0.8, score=0.85),
        ])
        return retriever

    @pytest.fixture
    def pipeline(self, settings, mock_vector_searcher, mock_insight_retriever):
        return RetrievalPipeline(
            settings=settings,
            vector_searcher=mock_vector_searcher,
            insight_retriever=mock_insight_retriever,
        )

    @pytest.mark.asyncio
    async def test_retrieve_combines_results(self, pipeline):
        """Test that retrieve combines chunks and insights."""
        query = ParsedQuery(
            original_query="What are the risks?",
            normalized_query="what are the risks",
            intent=QueryIntent.RISK,
            confidence=0.9,
        )

        result = await pipeline.retrieve(query, uuid4())

        assert result.has_results
        assert len(result.document_chunks) > 0
        assert len(result.insights) > 0

    @pytest.mark.asyncio
    async def test_retrieve_respects_flags(self, pipeline):
        """Test that include flags are respected."""
        query = ParsedQuery(
            original_query="test",
            normalized_query="test",
            intent=QueryIntent.FACTUAL,
            confidence=0.5,
        )

        result = await pipeline.retrieve(
            query, uuid4(),
            include_chunks=True,
            include_insights=False,
        )

        assert len(result.document_chunks) > 0
        # Insights should be empty when not included
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/retrieval/ -v`
2. Verify imports: `python -c "from aswa_query.retrieval import RetrievalPipeline"`
3. Test with mock data
