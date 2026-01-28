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
            async def empty_list():
                return []
            tasks.append(empty_list())

        if include_insights:
            tasks.append(self._retrieve_insights(query, tenant_id, max_insights))
        else:
            async def empty_list():
                return []
            tasks.append(empty_list())

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
