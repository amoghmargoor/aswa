"""Document processing pipeline components."""

from aswa_ingestion.processing.parser import DocumentParser, ParsedDocument, DocumentElement
from aswa_ingestion.processing.chunker import TextChunker, TextChunk, SemanticChunker
from aswa_ingestion.processing.embedder import EmbeddingClient
from aswa_ingestion.processing.deduplicator import (
    DocumentDeduplicator,
    DuplicateCheckResult,
)
from aswa_ingestion.processing.pipeline import (
    DocumentProcessingPipeline,
    ProcessingResult,
)

__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "DocumentElement",
    "TextChunker",
    "TextChunk",
    "SemanticChunker",
    "EmbeddingClient",
    "DocumentDeduplicator",
    "DuplicateCheckResult",
    "DocumentProcessingPipeline",
    "ProcessingResult",
]
