# Task 3.3.2: Map-Reduce for Long Documents

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The structured extraction system is implemented at `/services/insight-engine/src/aswa_insight/extraction/`. Documents can exceed LLM context windows, requiring a map-reduce strategy for extraction.

## Objective

Implement a map-reduce extraction pipeline for handling long documents that:
1. Intelligently chunks documents while preserving context
2. Extracts insights from each chunk (map phase)
3. Merges and deduplicates results across chunks (reduce phase)
4. Handles overlap between chunks to avoid missing insights at boundaries

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/chunking/__init__.py`
```python
from .splitter import TextSplitter, ChunkingStrategy, Chunk
from .context import ChunkContextBuilder, ChunkContext

__all__ = [
    "TextSplitter",
    "ChunkingStrategy",
    "Chunk",
    "ChunkContextBuilder",
    "ChunkContext",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/chunking/splitter.py`
Document chunking with various strategies:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
import re
import structlog

logger = structlog.get_logger()


class ChunkingStrategy(str, Enum):
    """Strategies for chunking text."""
    FIXED_SIZE = "fixed_size"           # Fixed character count
    SENTENCE = "sentence"                # Split on sentence boundaries
    PARAGRAPH = "paragraph"              # Split on paragraph boundaries
    SECTION = "section"                  # Split on section headers
    SEMANTIC = "semantic"                # Split on semantic boundaries
    RECURSIVE = "recursive"              # Recursively split large chunks


@dataclass
class Chunk:
    """A chunk of text from a document."""
    index: int
    text: str
    start_offset: int
    end_offset: int
    metadata: dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class TextSplitter:
    """Split text into chunks for processing."""

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """Initialize text splitter.

        Args:
            strategy: Chunking strategy to use
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            min_chunk_size: Minimum chunk size to keep
        """
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Regex patterns for splitting
        self._section_pattern = re.compile(r'\n(?=#{1,3}\s|\d+\.\s|[A-Z][A-Z\s]+:)')
        self._paragraph_pattern = re.compile(r'\n\s*\n')
        self._sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

    def split(self, text: str) -> list[Chunk]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of chunks
        """
        if len(text) <= self.chunk_size:
            return [Chunk(index=0, text=text, start_offset=0, end_offset=len(text))]

        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._split_fixed(text)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._split_sentences(text)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._split_paragraphs(text)
        elif self.strategy == ChunkingStrategy.SECTION:
            return self._split_sections(text)
        elif self.strategy == ChunkingStrategy.RECURSIVE:
            return self._split_recursive(text)
        else:
            return self._split_fixed(text)

    def _split_fixed(self, text: str) -> list[Chunk]:
        """Split into fixed-size chunks with overlap."""
        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to end at a sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start + self.min_chunk_size, end)
                if last_period > start:
                    end = last_period + 1

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    index=index,
                    text=chunk_text,
                    start_offset=start,
                    end_offset=end,
                ))
                index += 1

            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    def _split_sentences(self, text: str) -> list[Chunk]:
        """Split on sentence boundaries."""
        sentences = self._sentence_pattern.split(text)
        return self._merge_small_chunks(sentences, text)

    def _split_paragraphs(self, text: str) -> list[Chunk]:
        """Split on paragraph boundaries."""
        paragraphs = self._paragraph_pattern.split(text)
        return self._merge_small_chunks(paragraphs, text)

    def _split_sections(self, text: str) -> list[Chunk]:
        """Split on section headers."""
        sections = self._section_pattern.split(text)
        return self._merge_small_chunks(sections, text)

    def _split_recursive(self, text: str) -> list[Chunk]:
        """Recursively split using multiple strategies.

        Start with sections, then paragraphs, then sentences, then fixed.
        """
        # First, try sections
        sections = self._section_pattern.split(text)
        if len(sections) > 1:
            chunks = []
            for section in sections:
                if len(section) > self.chunk_size:
                    chunks.extend(self._split_recursive_inner(section, level=1))
                elif len(section.strip()) >= self.min_chunk_size:
                    chunks.append(section)
            return self._create_chunks_with_offsets(chunks, text)

        return self._split_recursive_inner(text, level=0)

    def _split_recursive_inner(self, text: str, level: int) -> list[str]:
        """Inner recursive splitting."""
        if len(text) <= self.chunk_size:
            return [text] if len(text.strip()) >= self.min_chunk_size else []

        if level == 0:
            # Try sections
            parts = self._section_pattern.split(text)
        elif level == 1:
            # Try paragraphs
            parts = self._paragraph_pattern.split(text)
        elif level == 2:
            # Try sentences
            parts = self._sentence_pattern.split(text)
        else:
            # Fall back to fixed size
            return [c.text for c in self._split_fixed(text)]

        if len(parts) <= 1:
            return self._split_recursive_inner(text, level + 1)

        result = []
        for part in parts:
            if len(part) > self.chunk_size:
                result.extend(self._split_recursive_inner(part, level + 1))
            elif len(part.strip()) >= self.min_chunk_size:
                result.append(part)

        return result

    def _merge_small_chunks(self, parts: list[str], original_text: str) -> list[Chunk]:
        """Merge small parts into larger chunks."""
        chunks = []
        current_text = ""
        current_start = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(current_text) + len(part) + 1 <= self.chunk_size:
                if current_text:
                    current_text += "\n\n" + part
                else:
                    current_text = part
                    current_start = original_text.find(part)
            else:
                if current_text and len(current_text) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        index=len(chunks),
                        text=current_text,
                        start_offset=current_start,
                        end_offset=current_start + len(current_text),
                    ))
                current_text = part
                current_start = original_text.find(part)

        # Add last chunk
        if current_text and len(current_text) >= self.min_chunk_size:
            chunks.append(Chunk(
                index=len(chunks),
                text=current_text,
                start_offset=current_start,
                end_offset=current_start + len(current_text),
            ))

        return chunks

    def _create_chunks_with_offsets(self, texts: list[str], original_text: str) -> list[Chunk]:
        """Create chunks with offset tracking."""
        chunks = []
        search_start = 0

        for i, text in enumerate(texts):
            text = text.strip()
            if len(text) < self.min_chunk_size:
                continue

            start = original_text.find(text, search_start)
            if start == -1:
                start = search_start

            chunks.append(Chunk(
                index=len(chunks),
                text=text,
                start_offset=start,
                end_offset=start + len(text),
            ))
            search_start = start + len(text)

        return chunks

    def get_token_estimate(self, chunk: Chunk) -> int:
        """Estimate token count for a chunk."""
        # Rough estimate: ~4 chars per token
        return len(chunk.text) // 4
```

### 3. Create `/services/insight-engine/src/aswa_insight/chunking/context.py`
Context preservation for chunks:

```python
from dataclasses import dataclass, field
from typing import Any
import structlog

from .splitter import Chunk

logger = structlog.get_logger()


@dataclass
class ChunkContext:
    """Context information for a chunk."""
    chunk: Chunk
    document_title: str | None = None
    document_summary: str | None = None
    previous_chunk_summary: str | None = None
    section_title: str | None = None
    position_description: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Convert to context string for prompts."""
        parts = []

        if self.document_title:
            parts.append(f"Document: {self.document_title}")

        if self.document_summary:
            parts.append(f"Document Summary: {self.document_summary}")

        if self.section_title:
            parts.append(f"Section: {self.section_title}")

        if self.position_description:
            parts.append(f"Position: {self.position_description}")

        if self.previous_chunk_summary:
            parts.append(f"Previous Content: {self.previous_chunk_summary}")

        return "\n".join(parts)


class ChunkContextBuilder:
    """Build context for chunks to preserve document understanding."""

    def __init__(
        self,
        include_document_summary: bool = True,
        include_position: bool = True,
        include_previous_summary: bool = True,
        max_summary_length: int = 500,
    ):
        self.include_document_summary = include_document_summary
        self.include_position = include_position
        self.include_previous_summary = include_previous_summary
        self.max_summary_length = max_summary_length

    def build_contexts(
        self,
        chunks: list[Chunk],
        document_title: str | None = None,
        document_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[ChunkContext]:
        """Build context for all chunks.

        Args:
            chunks: List of chunks
            document_title: Optional document title
            document_summary: Optional document summary
            metadata: Optional document metadata

        Returns:
            List of chunk contexts
        """
        contexts = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            # Position description
            position = None
            if self.include_position:
                if total_chunks == 1:
                    position = "Entire document"
                elif i == 0:
                    position = f"Beginning of document (chunk 1 of {total_chunks})"
                elif i == total_chunks - 1:
                    position = f"End of document (chunk {i + 1} of {total_chunks})"
                else:
                    position = f"Middle of document (chunk {i + 1} of {total_chunks})"

            # Previous chunk summary
            prev_summary = None
            if self.include_previous_summary and i > 0:
                prev_summary = self._create_chunk_summary(chunks[i - 1])

            # Detect section title if present
            section_title = self._detect_section_title(chunk.text)

            context = ChunkContext(
                chunk=chunk,
                document_title=document_title,
                document_summary=document_summary if self.include_document_summary else None,
                previous_chunk_summary=prev_summary,
                section_title=section_title,
                position_description=position,
                metadata=metadata or {},
            )
            contexts.append(context)

        return contexts

    def _create_chunk_summary(self, chunk: Chunk) -> str:
        """Create a brief summary of a chunk for context."""
        text = chunk.text[:self.max_summary_length]

        # Truncate at sentence boundary
        last_period = text.rfind('.')
        if last_period > self.max_summary_length // 2:
            text = text[:last_period + 1]

        return text.strip() + "..."

    def _detect_section_title(self, text: str) -> str | None:
        """Detect section title from chunk start."""
        lines = text.strip().split('\n')
        if not lines:
            return None

        first_line = lines[0].strip()

        # Check for markdown headers
        if first_line.startswith('#'):
            return first_line.lstrip('#').strip()

        # Check for numbered headers
        if len(first_line) < 100 and first_line[0].isdigit():
            return first_line

        # Check for ALL CAPS headers
        if first_line.isupper() and len(first_line) < 100:
            return first_line

        return None
```

### 4. Create `/services/insight-engine/src/aswa_insight/extraction/mapreduce.py`
Map-reduce extraction pipeline:

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog

from aswa_insight.chunking.splitter import TextSplitter, Chunk, ChunkingStrategy
from aswa_insight.chunking.context import ChunkContextBuilder, ChunkContext
from aswa_insight.extraction.extractor import StructuredExtractor, ExtractionResult
from aswa_insight.models.base import ExtractedInsightBase
from aswa_insight.models.insights import Insight
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
                chunk_results=[ChunkExtractionResult(
                    chunk=chunks[0],
                    context=ChunkContext(chunk=chunks[0]),
                    extraction_result=result,
                )],
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
        results = []
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
                processed.append(ChunkExtractionResult(
                    chunk=chunk_contexts[i].chunk,
                    context=chunk_contexts[i],
                    extraction_result=ExtractionResult(
                        success=False,
                        error=str(result),
                    ),
                ))
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

        for field in ["entities", "risks", "opportunities", "patterns"]:
            if field in data and isinstance(data[field], list):
                return data[field]

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
```

## Test Requirements

### Create `/services/insight-engine/tests/chunking/__init__.py`

### Create `/services/insight-engine/tests/chunking/test_splitter.py`
```python
import pytest
from aswa_insight.chunking.splitter import TextSplitter, ChunkingStrategy, Chunk


class TestTextSplitter:
    def test_short_text_single_chunk(self):
        """Test short text returns single chunk."""
        splitter = TextSplitter(chunk_size=1000)
        text = "This is a short text."
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_fixed_size_chunking(self):
        """Test fixed size chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=100,
            chunk_overlap=20,
        )
        text = "A" * 500
        chunks = splitter.split(text)
        assert len(chunks) > 1
        # Check overlap
        assert chunks[0].end_offset > chunks[1].start_offset

    def test_sentence_chunking(self):
        """Test sentence-based chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=100,
        )
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = splitter.split(text)
        # Should split on sentence boundaries
        for chunk in chunks:
            assert chunk.text.endswith('.') or chunk.text.endswith('...')

    def test_paragraph_chunking(self):
        """Test paragraph-based chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=200,
        )
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_recursive_chunking(self):
        """Test recursive chunking strategy."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=200,
        )
        text = "# Section 1\n\nParagraph 1.\n\n# Section 2\n\nParagraph 2."
        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_chunk_offsets_correct(self):
        """Test chunk offsets are correct."""
        splitter = TextSplitter(chunk_size=100)
        text = "A" * 300
        chunks = splitter.split(text)

        for chunk in chunks:
            assert chunk.start_offset >= 0
            assert chunk.end_offset <= len(text)
            assert chunk.start_offset < chunk.end_offset

    def test_min_chunk_size_respected(self):
        """Test minimum chunk size is respected."""
        splitter = TextSplitter(
            chunk_size=100,
            min_chunk_size=50,
        )
        text = "Short.\n\n" + "A" * 200
        chunks = splitter.split(text)

        for chunk in chunks:
            assert len(chunk.text) >= splitter.min_chunk_size


class TestChunk:
    def test_chunk_properties(self):
        """Test chunk properties."""
        chunk = Chunk(
            index=0,
            text="Hello world test",
            start_offset=0,
            end_offset=16,
        )
        assert chunk.length == 16
        assert chunk.word_count == 3
```

### Create `/services/insight-engine/tests/chunking/test_context.py`
```python
import pytest
from aswa_insight.chunking.splitter import Chunk
from aswa_insight.chunking.context import ChunkContextBuilder, ChunkContext


class TestChunkContextBuilder:
    def test_build_single_chunk_context(self):
        """Test context for single chunk."""
        builder = ChunkContextBuilder()
        chunks = [Chunk(index=0, text="Test content", start_offset=0, end_offset=12)]

        contexts = builder.build_contexts(chunks, document_title="Test Doc")

        assert len(contexts) == 1
        assert contexts[0].document_title == "Test Doc"
        assert "Entire document" in contexts[0].position_description

    def test_build_multiple_chunk_contexts(self):
        """Test context for multiple chunks."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(index=0, text="First chunk", start_offset=0, end_offset=11),
            Chunk(index=1, text="Second chunk", start_offset=11, end_offset=23),
            Chunk(index=2, text="Third chunk", start_offset=23, end_offset=34),
        ]

        contexts = builder.build_contexts(chunks)

        assert len(contexts) == 3
        assert "Beginning" in contexts[0].position_description
        assert "Middle" in contexts[1].position_description
        assert "End" in contexts[2].position_description

    def test_previous_chunk_summary(self):
        """Test previous chunk summary is included."""
        builder = ChunkContextBuilder(include_previous_summary=True)
        chunks = [
            Chunk(index=0, text="First chunk content here.", start_offset=0, end_offset=25),
            Chunk(index=1, text="Second chunk content.", start_offset=25, end_offset=46),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].previous_chunk_summary is None
        assert contexts[1].previous_chunk_summary is not None

    def test_detect_section_title(self):
        """Test section title detection."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(index=0, text="# Introduction\n\nThis is content.", start_offset=0, end_offset=30),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].section_title == "Introduction"


class TestChunkContext:
    def test_to_context_string(self):
        """Test context string generation."""
        context = ChunkContext(
            chunk=Chunk(index=0, text="Test", start_offset=0, end_offset=4),
            document_title="My Document",
            section_title="Introduction",
            position_description="Beginning",
        )

        context_str = context.to_context_string()

        assert "My Document" in context_str
        assert "Introduction" in context_str
        assert "Beginning" in context_str
```

### Create `/services/insight-engine/tests/extraction/test_mapreduce.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.extraction.mapreduce import MapReduceExtractor, MapReduceResult
from aswa_insight.extraction.extractor import StructuredExtractor, ExtractionResult
from aswa_insight.models.entities import EntityExtractionResult, ExtractedEntity, EntityType


class TestMapReduceExtractor:
    @pytest.fixture
    def mock_extractor(self):
        extractor = MagicMock(spec=StructuredExtractor)
        extractor.extract = AsyncMock()
        return extractor

    @pytest.fixture
    def mapreduce(self, mock_extractor):
        return MapReduceExtractor(
            extractor=mock_extractor,
            max_concurrent_chunks=2,
        )

    @pytest.mark.asyncio
    async def test_short_document_no_chunking(self, mapreduce, mock_extractor):
        """Test short document doesn't need chunking."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        result = await mapreduce.extract(
            text="Short text",
            extraction_type="entity",
        )

        assert result.total_chunks == 1
        assert result.success

    @pytest.mark.asyncio
    async def test_long_document_chunked(self, mapreduce, mock_extractor):
        """Test long document is chunked."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        # Create long text
        long_text = "Paragraph. " * 1000

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        assert result.total_chunks > 1

    @pytest.mark.asyncio
    async def test_deduplication(self, mapreduce, mock_extractor):
        """Test duplicate insights are deduplicated."""
        # Setup mock to return same entity from different chunks
        entity = {"name": "Test Corp", "entity_type": "organization", "confidence": 0.8}

        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=MagicMock(model_dump=lambda: {"entities": [entity]}),
        )

        long_text = "Test Corp is mentioned. " * 500

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        # Should deduplicate
        assert result.deduplication_stats["removed"] >= 0

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, mapreduce, mock_extractor):
        """Test handling of partial chunk failures."""
        call_count = 0

        async def mock_extract(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return ExtractionResult(success=False, error="Chunk failed")
            return ExtractionResult(
                success=True,
                result=EntityExtractionResult(entities=[]),
            )

        mock_extractor.extract = mock_extract

        long_text = "Content. " * 500

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        assert result.failed_chunks >= 1
        assert len(result.errors) >= 1


class TestMapReduceResult:
    def test_success_all_passed(self):
        """Test success when all chunks pass."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=3,
            failed_chunks=0,
        )
        assert result.success is True

    def test_success_partial_pass(self):
        """Test success with partial failures."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=2,
            failed_chunks=1,
        )
        assert result.success is True  # At least some succeeded

    def test_failure_all_failed(self):
        """Test failure when all chunks fail."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=0,
            failed_chunks=3,
        )
        assert result.success is False
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/chunking/ tests/extraction/test_mapreduce.py -v`
2. Verify imports: `python -c "from aswa_insight.chunking import *; from aswa_insight.extraction.mapreduce import MapReduceExtractor"`
3. Test with sample long document
