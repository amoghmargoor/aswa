"""Tests for document processing handlers."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from aswa_processor.handlers import (
    DocumentProcessingHandler,
    BatchDocumentHandler,
    ReindexHandler,
)


TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")
TEST_DOCUMENT_ID = UUID("87654321-4321-4321-4321-cba987654321")


@dataclass
class MockDocument:
    """Mock document for testing."""

    id: UUID
    tenant_id: UUID
    name: str = "test.pdf"
    content_type: str = "application/pdf"
    processed_status: str = "pending"


@dataclass
class MockProcessingResult:
    """Mock processing result."""

    chunks_created: int = 10
    vectors_stored: int = 10
    processing_time_ms: int = 100


class TestDocumentProcessingHandler:
    """Tests for DocumentProcessingHandler."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(
        self, mock_session: AsyncMock
    ) -> Any:
        """Create mock session factory."""
        @asynccontextmanager
        async def factory() -> AsyncGenerator[AsyncMock, None]:
            yield mock_session

        return factory

    @pytest.fixture
    def mock_pipeline(self) -> AsyncMock:
        """Create mock pipeline."""
        pipeline = AsyncMock()
        pipeline.process = AsyncMock(return_value=MockProcessingResult())
        return pipeline

    @pytest.fixture
    def mock_repository_cls(self) -> type:
        """Create mock repository class."""
        mock_doc = MockDocument(id=TEST_DOCUMENT_ID, tenant_id=TEST_TENANT_ID)

        class MockRepo:
            def __init__(self, session: Any, tenant_id: UUID) -> None:
                self.session = session
                self.tenant_id = tenant_id

            async def get_by_id(self, doc_id: UUID) -> MockDocument | None:
                if doc_id == TEST_DOCUMENT_ID:
                    return mock_doc
                return None

            async def update_status(
                self, doc_id: UUID, status: str, error: str | None = None
            ) -> None:
                mock_doc.processed_status = status

        return MockRepo

    @pytest.fixture
    def handler(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
        mock_repository_cls: type,
    ) -> DocumentProcessingHandler:
        """Create handler with mocks."""
        return DocumentProcessingHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
            repository_cls=mock_repository_cls,
        )

    @pytest.mark.asyncio
    async def test_process_document_success(
        self, handler: DocumentProcessingHandler, mock_pipeline: AsyncMock
    ) -> None:
        """Test successful document processing."""
        payload = {
            "document_id": str(TEST_DOCUMENT_ID),
            "tenant_id": str(TEST_TENANT_ID),
        }

        await handler(payload)

        mock_pipeline.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_not_found(
        self, handler: DocumentProcessingHandler, mock_pipeline: AsyncMock
    ) -> None:
        """Test handling of non-existent document."""
        payload = {
            "document_id": str(uuid4()),  # Non-existent
            "tenant_id": str(TEST_TENANT_ID),
        }

        await handler(payload)

        # Pipeline should not be called for non-existent document
        mock_pipeline.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_already_processed(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test skipping already processed documents."""
        completed_doc = MockDocument(
            id=TEST_DOCUMENT_ID,
            tenant_id=TEST_TENANT_ID,
            processed_status="completed",
        )

        class MockRepo:
            def __init__(self, session: Any, tenant_id: UUID) -> None:
                pass

            async def get_by_id(self, doc_id: UUID) -> MockDocument:
                return completed_doc

            async def update_status(
                self, doc_id: UUID, status: str, error: str | None = None
            ) -> None:
                pass

        handler = DocumentProcessingHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
            repository_cls=MockRepo,
        )

        payload = {
            "document_id": str(TEST_DOCUMENT_ID),
            "tenant_id": str(TEST_TENANT_ID),
            "reprocess": False,
        }

        await handler(payload)

        # Should skip processing
        mock_pipeline.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_reprocess_completed_document(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test reprocessing completed document with reprocess flag."""
        completed_doc = MockDocument(
            id=TEST_DOCUMENT_ID,
            tenant_id=TEST_TENANT_ID,
            processed_status="completed",
        )

        class MockRepo:
            def __init__(self, session: Any, tenant_id: UUID) -> None:
                pass

            async def get_by_id(self, doc_id: UUID) -> MockDocument:
                return completed_doc

            async def update_status(
                self, doc_id: UUID, status: str, error: str | None = None
            ) -> None:
                completed_doc.processed_status = status

        handler = DocumentProcessingHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
            repository_cls=MockRepo,
        )

        payload = {
            "document_id": str(TEST_DOCUMENT_ID),
            "tenant_id": str(TEST_TENANT_ID),
            "reprocess": True,
        }

        await handler(payload)

        # Should process despite being completed
        mock_pipeline.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_processing_failure_updates_status(
        self,
        mock_session_factory: Any,
    ) -> None:
        """Test that processing failure updates status to failed."""
        doc = MockDocument(id=TEST_DOCUMENT_ID, tenant_id=TEST_TENANT_ID)
        status_updates: list[tuple[UUID, str]] = []

        class MockRepo:
            def __init__(self, session: Any, tenant_id: UUID) -> None:
                pass

            async def get_by_id(self, doc_id: UUID) -> MockDocument:
                return doc

            async def update_status(
                self, doc_id: UUID, status: str, error: str | None = None
            ) -> None:
                status_updates.append((doc_id, status))

        failing_pipeline = AsyncMock()
        failing_pipeline.process = AsyncMock(side_effect=ValueError("Processing failed"))

        handler = DocumentProcessingHandler(
            session_factory=mock_session_factory,
            pipeline=failing_pipeline,
            repository_cls=MockRepo,
        )

        payload = {
            "document_id": str(TEST_DOCUMENT_ID),
            "tenant_id": str(TEST_TENANT_ID),
        }

        with pytest.raises(ValueError):
            await handler(payload)

        # Should have updated to processing then failed
        assert len(status_updates) == 2
        assert status_updates[0][1] == "processing"
        assert status_updates[1][1] == "failed"

    @pytest.mark.asyncio
    async def test_missing_document_id_raises(
        self, handler: DocumentProcessingHandler
    ) -> None:
        """Test that missing document_id raises ValueError."""
        payload = {"tenant_id": str(TEST_TENANT_ID)}

        with pytest.raises(ValueError, match="document_id"):
            await handler(payload)

    @pytest.mark.asyncio
    async def test_missing_tenant_id_raises(
        self, handler: DocumentProcessingHandler
    ) -> None:
        """Test that missing tenant_id raises ValueError."""
        payload = {"document_id": str(TEST_DOCUMENT_ID)}

        with pytest.raises(ValueError, match="tenant_id"):
            await handler(payload)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(
        self, handler: DocumentProcessingHandler
    ) -> None:
        """Test that invalid UUID raises ValueError."""
        payload = {
            "document_id": "not-a-uuid",
            "tenant_id": str(TEST_TENANT_ID),
        }

        with pytest.raises(ValueError, match="Invalid UUID"):
            await handler(payload)


class TestBatchDocumentHandler:
    """Tests for BatchDocumentHandler."""

    @pytest.fixture
    def mock_session_factory(self) -> Any:
        """Create mock session factory."""
        @asynccontextmanager
        async def factory() -> AsyncGenerator[AsyncMock, None]:
            yield AsyncMock()

        return factory

    @pytest.fixture
    def mock_pipeline(self) -> AsyncMock:
        """Create mock pipeline."""
        pipeline = AsyncMock()
        pipeline.process = AsyncMock(return_value=MockProcessingResult())
        return pipeline

    @pytest.mark.asyncio
    async def test_batch_processes_all_documents(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test batch handler processes all documents."""
        docs = [
            MockDocument(id=uuid4(), tenant_id=TEST_TENANT_ID)
            for _ in range(3)
        ]
        process_count = 0

        class MockRepo:
            def __init__(self, session: Any, tenant_id: UUID) -> None:
                self.doc_index = 0

            async def get_by_id(self, doc_id: UUID) -> MockDocument:
                for doc in docs:
                    if doc.id == doc_id:
                        return doc
                return None

            async def update_status(
                self, doc_id: UUID, status: str, error: str | None = None
            ) -> None:
                nonlocal process_count
                if status == "completed":
                    process_count += 1

        # Create single handler with mock repo
        single_handler = DocumentProcessingHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
            repository_cls=MockRepo,
        )

        batch_handler = BatchDocumentHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
        )
        batch_handler._single_handler = single_handler

        payload = {
            "documents": [
                {"document_id": str(doc.id), "tenant_id": str(TEST_TENANT_ID)}
                for doc in docs
            ]
        }

        await batch_handler(payload)

        assert mock_pipeline.process.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_handles_empty_payload(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test batch handler handles empty payload."""
        handler = BatchDocumentHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
        )

        await handler({"documents": []})

        mock_pipeline.process.assert_not_called()


class TestReindexHandler:
    """Tests for ReindexHandler."""

    @pytest.fixture
    def mock_session_factory(self) -> Any:
        """Create mock session factory."""
        @asynccontextmanager
        async def factory() -> AsyncGenerator[AsyncMock, None]:
            yield AsyncMock()

        return factory

    @pytest.fixture
    def mock_pipeline(self) -> AsyncMock:
        """Create mock pipeline."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_reindex_handler_called(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test reindex handler can be called."""
        handler = ReindexHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
        )

        payload = {
            "tenant_id": str(TEST_TENANT_ID),
            "document_ids": [str(uuid4()), str(uuid4())],
            "force": True,
        }

        # Should not raise
        await handler(payload)

    @pytest.mark.asyncio
    async def test_reindex_all_documents(
        self,
        mock_session_factory: Any,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test reindex without document_ids processes all."""
        handler = ReindexHandler(
            session_factory=mock_session_factory,
            pipeline=mock_pipeline,
        )

        payload = {
            "tenant_id": str(TEST_TENANT_ID),
        }

        # Should not raise
        await handler(payload)
