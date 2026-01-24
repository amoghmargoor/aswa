"""Tests for document processing pipeline."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from aswa_ingestion.processing.pipeline import (
    DocumentProcessingPipeline,
    ProcessingResult,
)
from aswa_ingestion.processing.parser import ParsedDocument, DocumentElement
from aswa_ingestion.processing.chunker import TextChunk
from aswa_ingestion.processing.deduplicator import DuplicateCheckResult


class TestProcessingResult:
    """Tests for ProcessingResult model."""

    def test_success_result(self) -> None:
        """Test successful processing result."""
        result = ProcessingResult(
            document_id=uuid4(),
            success=True,
            chunks_created=10,
            vectors_stored=10,
            processing_time_ms=500,
        )

        assert result.success is True
        assert result.error is None
        assert result.chunks_created == 10

    def test_failure_result(self) -> None:
        """Test failed processing result."""
        result = ProcessingResult(
            document_id=uuid4(),
            success=False,
            error="Processing failed",
            processing_time_ms=100,
        )

        assert result.success is False
        assert result.error == "Processing failed"
        assert result.chunks_created == 0


class TestDocumentProcessingPipeline:
    """Tests for DocumentProcessingPipeline class."""

    @pytest.fixture
    def mock_parser(self) -> AsyncMock:
        """Create mock parser."""
        parser = AsyncMock()
        parser.parse = AsyncMock(
            return_value=ParsedDocument(
                text="Test document content.",
                elements=[
                    DocumentElement(
                        type="narrative_text",
                        text="Test document content.",
                    )
                ],
                metadata={},
                word_count=3,
            )
        )
        return parser

    @pytest.fixture
    def mock_chunker(self) -> MagicMock:
        """Create mock chunker."""
        chunker = MagicMock()
        chunker.chunk_with_metadata = MagicMock(
            return_value=[
                TextChunk(
                    content="Test document content.",
                    token_count=5,
                    start_char=0,
                    end_char=22,
                )
            ]
        )
        return chunker

    @pytest.fixture
    def mock_embedder(self) -> AsyncMock:
        """Create mock embedder."""
        embedder = AsyncMock()
        embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        return embedder

    @pytest.fixture
    def mock_deduplicator(self) -> AsyncMock:
        """Create mock deduplicator."""
        deduplicator = MagicMock()
        deduplicator.check_duplicate = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                duplicate_type="none",
            )
        )
        deduplicator.compute_minhash = MagicMock()
        deduplicator.add_to_index = MagicMock()
        return deduplicator

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        """Create mock vector store."""
        store = AsyncMock()
        store.upsert = AsyncMock()
        store.delete = AsyncMock()
        return store

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.get = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_document(self) -> MagicMock:
        """Create mock document."""
        doc = MagicMock()
        doc.id = uuid4()
        doc.tenant_id = uuid4()
        doc.data_source_id = uuid4()
        doc.title = "Test Document"
        doc.content = "Test document content."
        doc.content_type = "text/plain"
        doc.processed_status = "pending"
        return doc

    @pytest.fixture
    def pipeline(
        self,
        mock_parser: AsyncMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_deduplicator: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_db: AsyncMock,
    ) -> DocumentProcessingPipeline:
        """Create pipeline instance."""
        return DocumentProcessingPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            deduplicator=mock_deduplicator,
            vector_store=mock_vector_store,
            db=mock_db,
        )


class TestProcess:
    """Tests for single document processing."""

    @pytest.fixture
    def mock_parser(self) -> AsyncMock:
        """Create mock parser."""
        parser = AsyncMock()
        parser.parse = AsyncMock(
            return_value=ParsedDocument(
                text="Test document content.",
                elements=[
                    DocumentElement(
                        type="narrative_text",
                        text="Test document content.",
                    )
                ],
                metadata={},
                word_count=3,
            )
        )
        return parser

    @pytest.fixture
    def mock_chunker(self) -> MagicMock:
        """Create mock chunker."""
        chunker = MagicMock()
        chunker.chunk_with_metadata = MagicMock(
            return_value=[
                TextChunk(
                    content="Test document content.",
                    token_count=5,
                    start_char=0,
                    end_char=22,
                )
            ]
        )
        return chunker

    @pytest.fixture
    def mock_embedder(self) -> AsyncMock:
        """Create mock embedder."""
        embedder = AsyncMock()
        embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        return embedder

    @pytest.fixture
    def mock_deduplicator(self) -> MagicMock:
        """Create mock deduplicator."""
        deduplicator = MagicMock()
        deduplicator.check_duplicate = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                duplicate_type="none",
            )
        )
        deduplicator.compute_minhash = MagicMock()
        deduplicator.add_to_index = MagicMock()
        return deduplicator

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        """Create mock vector store."""
        store = AsyncMock()
        store.upsert = AsyncMock()
        store.delete = AsyncMock()
        return store

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.get = AsyncMock(return_value=MagicMock())
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_document(self) -> MagicMock:
        """Create mock document."""
        doc = MagicMock()
        doc.id = uuid4()
        doc.tenant_id = uuid4()
        doc.data_source_id = uuid4()
        doc.title = "Test Document"
        doc.content = "Test document content."
        doc.content_type = "text/plain"
        doc.processed_status = "pending"
        return doc

    @pytest.fixture
    def pipeline(
        self,
        mock_parser: AsyncMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_deduplicator: MagicMock,
        mock_vector_store: AsyncMock,
        mock_db: AsyncMock,
    ) -> DocumentProcessingPipeline:
        """Create pipeline instance."""
        return DocumentProcessingPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            deduplicator=mock_deduplicator,
            vector_store=mock_vector_store,
            db=mock_db,
        )

    @pytest.mark.asyncio
    async def test_process_success(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_document: MagicMock,
        mock_parser: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test successful document processing."""
        result = await pipeline.process(mock_document)

        assert result.success is True
        assert result.document_id == mock_document.id
        assert result.chunks_created >= 1
        assert result.vectors_stored >= 1
        assert result.processing_time_ms > 0

        mock_parser.parse.assert_called_once()
        mock_embedder.embed_batch.assert_called_once()
        mock_vector_store.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_no_content(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_document: MagicMock,
    ) -> None:
        """Test processing document with no content."""
        mock_document.content = None

        result = await pipeline.process(mock_document)

        assert result.success is False
        assert "no content" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_exact_duplicate(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_document: MagicMock,
        mock_deduplicator: MagicMock,
    ) -> None:
        """Test processing detects exact duplicate."""
        duplicate_id = uuid4()
        mock_deduplicator.check_duplicate = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=True,
                duplicate_type="exact",
                duplicate_id=duplicate_id,
                similarity_score=1.0,
            )
        )

        result = await pipeline.process(mock_document)

        assert result.success is False
        assert "duplicate" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_no_chunks(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_document: MagicMock,
        mock_chunker: MagicMock,
    ) -> None:
        """Test processing document that produces no chunks."""
        mock_chunker.chunk_with_metadata = MagicMock(return_value=[])

        result = await pipeline.process(mock_document)

        assert result.success is True
        assert result.chunks_created == 0
        assert result.vectors_stored == 0

    @pytest.mark.asyncio
    async def test_process_parser_failure(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_document: MagicMock,
        mock_parser: AsyncMock,
    ) -> None:
        """Test handling parser failure."""
        mock_parser.parse = AsyncMock(side_effect=ValueError("Parse error"))

        result = await pipeline.process(mock_document)

        assert result.success is False
        assert "Parse error" in result.error


class TestProcessBatch:
    """Tests for batch document processing."""

    @pytest.fixture
    def mock_parser(self) -> AsyncMock:
        """Create mock parser."""
        parser = AsyncMock()
        parser.parse = AsyncMock(
            return_value=ParsedDocument(
                text="Test content.",
                elements=[],
                metadata={},
                word_count=2,
            )
        )
        return parser

    @pytest.fixture
    def mock_chunker(self) -> MagicMock:
        """Create mock chunker."""
        chunker = MagicMock()
        chunker.chunk_with_metadata = MagicMock(
            return_value=[
                TextChunk(
                    content="Test content.",
                    token_count=3,
                    start_char=0,
                    end_char=13,
                )
            ]
        )
        return chunker

    @pytest.fixture
    def mock_embedder(self) -> AsyncMock:
        """Create mock embedder."""
        embedder = AsyncMock()
        embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        return embedder

    @pytest.fixture
    def mock_deduplicator(self) -> MagicMock:
        """Create mock deduplicator."""
        deduplicator = MagicMock()
        deduplicator.check_duplicate = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                duplicate_type="none",
            )
        )
        deduplicator.compute_minhash = MagicMock()
        deduplicator.add_to_index = MagicMock()
        return deduplicator

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        """Create mock vector store."""
        store = AsyncMock()
        store.upsert = AsyncMock()
        return store

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.get = AsyncMock(return_value=MagicMock())
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def pipeline(
        self,
        mock_parser: AsyncMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_deduplicator: MagicMock,
        mock_vector_store: AsyncMock,
        mock_db: AsyncMock,
    ) -> DocumentProcessingPipeline:
        """Create pipeline instance."""
        return DocumentProcessingPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            deduplicator=mock_deduplicator,
            vector_store=mock_vector_store,
            db=mock_db,
        )

    @pytest.mark.asyncio
    async def test_process_batch_empty(
        self,
        pipeline: DocumentProcessingPipeline,
    ) -> None:
        """Test processing empty batch."""
        results = await pipeline.process_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_process_batch_multiple(
        self,
        pipeline: DocumentProcessingPipeline,
    ) -> None:
        """Test processing multiple documents."""
        docs = []
        for i in range(3):
            doc = MagicMock()
            doc.id = uuid4()
            doc.tenant_id = uuid4()
            doc.data_source_id = uuid4()
            doc.title = f"Document {i}"
            doc.content = f"Content {i}"
            doc.content_type = "text/plain"
            docs.append(doc)

        results = await pipeline.process_batch(docs, concurrency=2)

        assert len(results) == 3
        assert all(isinstance(r, ProcessingResult) for r in results)


class TestReprocess:
    """Tests for document reprocessing."""

    @pytest.fixture
    def mock_parser(self) -> AsyncMock:
        """Create mock parser."""
        parser = AsyncMock()
        parser.parse = AsyncMock(
            return_value=ParsedDocument(
                text="Reprocessed content.",
                elements=[],
                metadata={},
                word_count=2,
            )
        )
        return parser

    @pytest.fixture
    def mock_chunker(self) -> MagicMock:
        """Create mock chunker."""
        chunker = MagicMock()
        chunker.chunk_with_metadata = MagicMock(
            return_value=[
                TextChunk(
                    content="Reprocessed content.",
                    token_count=3,
                    start_char=0,
                    end_char=20,
                )
            ]
        )
        return chunker

    @pytest.fixture
    def mock_embedder(self) -> AsyncMock:
        """Create mock embedder."""
        embedder = AsyncMock()
        embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        return embedder

    @pytest.fixture
    def mock_deduplicator(self) -> MagicMock:
        """Create mock deduplicator."""
        deduplicator = MagicMock()
        deduplicator.check_duplicate = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                duplicate_type="none",
            )
        )
        deduplicator.compute_minhash = MagicMock()
        deduplicator.add_to_index = MagicMock()
        deduplicator.remove_from_index = MagicMock()
        return deduplicator

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        """Create mock vector store."""
        store = AsyncMock()
        store.upsert = AsyncMock()
        store.delete = AsyncMock()
        return store

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def pipeline(
        self,
        mock_parser: AsyncMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_deduplicator: MagicMock,
        mock_vector_store: AsyncMock,
        mock_db: AsyncMock,
    ) -> DocumentProcessingPipeline:
        """Create pipeline instance."""
        return DocumentProcessingPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            deduplicator=mock_deduplicator,
            vector_store=mock_vector_store,
            db=mock_db,
        )

    @pytest.mark.asyncio
    async def test_reprocess_not_found(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_db: AsyncMock,
    ) -> None:
        """Test reprocessing non-existent document."""
        mock_db.get = AsyncMock(return_value=None)

        result = await pipeline.reprocess(uuid4())

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_reprocess_success(
        self,
        pipeline: DocumentProcessingPipeline,
        mock_db: AsyncMock,
        mock_deduplicator: MagicMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test successful reprocessing."""
        doc = MagicMock()
        doc.id = uuid4()
        doc.tenant_id = uuid4()
        doc.data_source_id = uuid4()
        doc.title = "Test Doc"
        doc.content = "Reprocessed content."
        doc.content_type = "text/plain"
        doc.processed_status = "completed"

        mock_db.get = AsyncMock(return_value=doc)

        result = await pipeline.reprocess(doc.id)

        # Should delete old chunks
        mock_db.execute.assert_called()
        # Should delete old vectors
        mock_vector_store.delete.assert_called_once()
        # Should remove from deduplicator index
        mock_deduplicator.remove_from_index.assert_called_once()
