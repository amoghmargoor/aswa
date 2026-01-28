import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog

from aswa_insight.chunking.context import ChunkContext, ChunkContextBuilder
from aswa_insight.chunking.splitter import Chunk, ChunkingStrategy, TextSplitter
from aswa_insight.extraction.extractor import ExtractionResult, StructuredExtractor
from aswa_insight.scoring.confidence import ConfidenceAggregator

logger = structlog.get_logger()


@dataclass
class ChunkExtractionResult:
    """Result from extracting a single chunk."""

    chunk: Chunk
    context: ChunkContext
    extraction_result: ExtractionResult
    insights: list[Any] = field(default_factory=list)


@dataclass
class MapReduceResult:
    """Result from map-reduce extraction."""

    document_id: UUID
    total_chunks: int
    successful_chunks: int
    failed_chunks: int
    chunk_results: list[ChunkExtractionResult] = field(default_factory=list)
    merged_insights: list[Any] = field(default_factory=list)
    deduplication_stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed_chunks == 0 or self.successful_chunks > 0


class MapReduceExtractor:
    """Map-reduce extraction for long documents."""

    def __init__(
        self,
        extractor: StructuredExtractor,
        splitter: TextSplitter | None = None,
        context_builder: ChunkContextBuilder | None = None,
        max_concurrent_chunks: int = 3,
        similarity_threshold: float = 0.85,
    ):
        """Initialize map-reduce extractor.

        Args:
            extractor: Structured extractor to use
            splitter: Text splitter (default: recursive strategy)
            context_builder: Chunk context builder
            max_concurrent_chunks: Max chunks to process in parallel
            similarity_threshold: Threshold for deduplication
        """
        self.extractor = extractor
        self.splitter = splitter or TextSplitter(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=4000,
            chunk_overlap=200,
        )
        self.context_builder = context_builder or ChunkContextBuilder()
        self.max_concurrent = max_concurrent_chunks
        self.similarity_threshold = similarity_threshold
        self.confidence_aggregator = ConfidenceAggregator()

    async def extract(
        self,
        text: str,
        extraction_type: str,
        document_id: UUID | None = None,
        document_title: str | None = None,
        document_summary: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> MapReduceResult:
        """Extract insights using map-reduce.

        Args:
            text: Full document text
            extraction_type: Type of extraction
            document_id: Optional document ID
            document_title: Optional document title
            document_summary: Optional document summary
            context: Optional extraction context

        Returns:
            MapReduceResult with merged insights
        """
        doc_id = document_id or uuid4()

        logger.info(
            "Starting map-reduce extraction",
            document_id=str(doc_id),
            extraction_type=extraction_type,
            text_length=len(text),
        )

        # Split document into chunks
        chunks = self.splitter.split(text)
        logger.info(f"Split document into {len(chunks)} chunks")

        if len(chunks) == 1:
            # No need for map-reduce, single chunk
            result = await self.extractor.extract(
                text=text,
                extraction_type=extraction_type,
                context=context,
                document_id=doc_id,
            )
            return MapReduceResult(
                document_id=doc_id,
                total_chunks=1,
                successful_chunks=1 if result.success else 0,
                failed_chunks=0 if result.success else 1,
                chunk_results=[
                    ChunkExtractionResult(
                        chunk=chunks[0],
                        context=ChunkContext(chunk=chunks[0]),
                        extraction_result=result,
                    )
                ],
                merged_insights=self._get_insights(result),
            )

        # Build contexts for chunks
        chunk_contexts = self.context_builder.build_contexts(
            chunks=chunks,
            document_title=document_title,
            document_summary=document_summary,
        )

        # Map phase: Extract from each chunk
        chunk_results = await self._map_phase(
            chunk_contexts=chunk_contexts,
            extraction_type=extraction_type,
            context=context,
            document_id=doc_id,
        )

        # Reduce phase: Merge and deduplicate
        merged_insights, dedup_stats = self._reduce_phase(chunk_results, extraction_type)

        # Count successes/failures
        successful = sum(1 for r in chunk_results if r.extraction_result.success)
        failed = len(chunk_results) - successful

        errors = [
            f"Chunk {r.chunk.index}: {r.extraction_result.error}"
            for r in chunk_results
            if not r.extraction_result.success and r.extraction_result.error
        ]

        logger.info(
            "Map-reduce extraction complete",
            document_id=str(doc_id),
            total_chunks=len(chunks),
            successful_chunks=successful,
            merged_insights=len(merged_insights),
        )

        return MapReduceResult(
            document_id=doc_id,
            total_chunks=len(chunks),
            successful_chunks=successful,
            failed_chunks=failed,
            chunk_results=chunk_results,
            merged_insights=merged_insights,
            deduplication_stats=dedup_stats,
            errors=errors,
        )

    async def _map_phase(
        self,
        chunk_contexts: list[ChunkContext],
        extraction_type: str,
        context: dict[str, Any] | None,
        document_id: UUID,
    ) -> list[ChunkExtractionResult]:
        """Map phase: extract from each chunk."""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def extract_chunk(chunk_ctx: ChunkContext) -> ChunkExtractionResult:
            async with semaphore:
                # Build context with chunk information
                chunk_context = context.copy() if context else {}
                chunk_context["chunk_position"] = chunk_ctx.position_description
                chunk_context["chunk_context"] = chunk_ctx.to_context_string()

                result = await self.extractor.extract(
                    text=chunk_ctx.chunk.text,
                    extraction_type=extraction_type,
                    context=chunk_context,
                    document_id=document_id,
                )

                return ChunkExtractionResult(
                    chunk=chunk_ctx.chunk,
                    context=chunk_ctx,
                    extraction_result=result,
                    insights=self._get_insights(result),
                )

        # Process chunks concurrently
        tasks = [extract_chunk(ctx) for ctx in chunk_contexts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Chunk {i} failed", error=str(result))
                processed.append(
                    ChunkExtractionResult(
                        chunk=chunk_contexts[i].chunk,
                        context=chunk_contexts[i],
                        extraction_result=ExtractionResult(
                            success=False,
                            error=str(result),
                        ),
                    )
                )
            else:
                processed.append(result)

        return processed

    def _reduce_phase(
        self,
        chunk_results: list[ChunkExtractionResult],
        extraction_type: str,
    ) -> tuple[list[Any], dict]:
        """Reduce phase: merge and deduplicate insights."""
        all_insights = []
        for result in chunk_results:
            all_insights.extend(result.insights)

        if not all_insights:
            return [], {"total_raw": 0, "after_dedup": 0, "removed": 0}

        # Deduplicate
        deduplicated = self._deduplicate_insights(all_insights, extraction_type)

        stats = {
            "total_raw": len(all_insights),
            "after_dedup": len(deduplicated),
            "removed": len(all_insights) - len(deduplicated),
        }

        return deduplicated, stats

    def _get_insights(self, result: ExtractionResult) -> list[Any]:
        """Extract insights list from result."""
        if not result.success or not result.result:
            return []

        data = result.result.model_dump() if hasattr(result.result, "model_dump") else {}

        for field_name in ["entities", "risks", "opportunities", "patterns"]:
            if field_name in data and isinstance(data[field_name], list):
                return data[field_name]

        return []

    def _deduplicate_insights(
        self,
        insights: list[Any],
        extraction_type: str,
    ) -> list[Any]:
        """Deduplicate insights based on similarity."""
        if not insights:
            return []

        # Group by title/name for efficiency
        seen = {}

        for insight in insights:
            # Get key field
            key = insight.get("title") or insight.get("name", "")
            key_normalized = key.lower().strip()

            if key_normalized in seen:
                # Check if we should keep the new one (higher confidence)
                existing = seen[key_normalized]
                existing_conf = existing.get("confidence", 0)
                new_conf = insight.get("confidence", 0)

                if new_conf > existing_conf:
                    seen[key_normalized] = insight
                elif new_conf == existing_conf:
                    # Merge sources/evidence
                    self._merge_insight_data(existing, insight)
            else:
                seen[key_normalized] = insight

        return list(seen.values())

    def _merge_insight_data(self, existing: dict, new: dict) -> None:
        """Merge data from duplicate insights."""
        # Merge sources
        if "sources" in new:
            existing_sources = existing.get("sources", [])
            for source in new.get("sources", []):
                if source not in existing_sources:
                    existing_sources.append(source)
            existing["sources"] = existing_sources

        # Merge evidence
        if "evidence" in new:
            existing_evidence = existing.get("evidence", [])
            for ev in new.get("evidence", []):
                if ev not in existing_evidence:
                    existing_evidence.append(ev)
            existing["evidence"] = existing_evidence

        # Update confidence to max
        existing["confidence"] = max(
            existing.get("confidence", 0),
            new.get("confidence", 0),
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings."""
        # Simple Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0
