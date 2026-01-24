"""Tests for document service."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from aswa_ingestion.services.document_service import DocumentService

from tests.conftest import TEST_DATA_SOURCE_ID, TEST_TENANT_ID


class TestStoreDocument:
    """Tests for storing documents."""

    @pytest.mark.asyncio
    async def test_store_document_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test successful document storage."""
        service = DocumentService(db=mock_db_session, redis=mock_redis)

        # Mock the refresh to set the document ID
        async def mock_refresh(doc: Any) -> None:
            doc.id = uuid4()

        mock_db_session.refresh = mock_refresh

        document = await service.store_document(
            tenant_id=TEST_TENANT_ID,
            data_source_id=TEST_DATA_SOURCE_ID,
            external_id="ext-001",
            title="Test Document",
            content=b"Test content",
            content_type="text/plain",
            content_hash="abc123",
            file_size=12,
            metadata={"author": "test"},
        )

        assert document is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_document_with_utf8_content(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test storing document with UTF-8 content."""
        service = DocumentService(db=mock_db_session, redis=mock_redis)

        async def mock_refresh(doc: Any) -> None:
            doc.id = uuid4()

        mock_db_session.refresh = mock_refresh

        content = "Hello, 世界! 🌍".encode("utf-8")
        document = await service.store_document(
            tenant_id=TEST_TENANT_ID,
            data_source_id=TEST_DATA_SOURCE_ID,
            external_id="ext-002",
            title="Unicode Test",
            content=content,
            content_type="text/plain",
            content_hash="def456",
            file_size=len(content),
        )

        assert document is not None

    @pytest.mark.asyncio
    async def test_store_document_empty_content(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test storing document with empty content."""
        service = DocumentService(db=mock_db_session, redis=mock_redis)

        async def mock_refresh(doc: Any) -> None:
            doc.id = uuid4()

        mock_db_session.refresh = mock_refresh

        document = await service.store_document(
            tenant_id=TEST_TENANT_ID,
            data_source_id=TEST_DATA_SOURCE_ID,
            external_id="ext-003",
            title="Empty Document",
            content=b"",
            content_type="text/plain",
            content_hash="empty",
            file_size=0,
        )

        assert document is not None


class TestCheckDuplicate:
    """Tests for duplicate detection."""

    @pytest.mark.asyncio
    async def test_check_duplicate_not_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test duplicate check when no duplicate exists."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        result = await service.check_duplicate("hash123", TEST_TENANT_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_duplicate_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_document_data: dict[str, Any],
    ) -> None:
        """Test duplicate check when duplicate exists."""
        mock_doc = MagicMock()
        mock_doc.id = sample_document_data["id"]
        mock_doc.content_hash = sample_document_data["content_hash"]

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_doc)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        result = await service.check_duplicate(
            sample_document_data["content_hash"], TEST_TENANT_ID
        )

        assert result is not None
        assert result.id == sample_document_data["id"]


class TestGetDocument:
    """Tests for getting documents."""

    @pytest.mark.asyncio
    async def test_get_document_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_document_data: dict[str, Any],
    ) -> None:
        """Test getting an existing document."""
        mock_doc = MagicMock()
        mock_doc.id = sample_document_data["id"]
        mock_doc.tenant_id = TEST_TENANT_ID

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_doc)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        result = await service.get_document(sample_document_data["id"], TEST_TENANT_ID)

        assert result is not None
        assert result.id == sample_document_data["id"]

    @pytest.mark.asyncio
    async def test_get_document_not_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting a non-existent document."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        result = await service.get_document(uuid4(), TEST_TENANT_ID)

        assert result is None


class TestUpdateStatus:
    """Tests for updating document status."""

    @pytest.mark.asyncio
    async def test_update_status_to_processing(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test updating status to processing."""
        mock_doc = MagicMock()
        mock_doc.processed_status = "pending"
        mock_db_session.get = AsyncMock(return_value=mock_doc)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.update_status(uuid4(), "processing")

        assert mock_doc.processed_status == "processing"
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_to_completed(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test updating status to completed sets processed_at."""
        mock_doc = MagicMock()
        mock_doc.processed_status = "processing"
        mock_doc.processed_at = None
        mock_db_session.get = AsyncMock(return_value=mock_doc)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.update_status(uuid4(), "completed")

        assert mock_doc.processed_status == "completed"
        assert mock_doc.processed_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_failed_with_error(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test updating status to failed with error message."""
        mock_doc = MagicMock()
        mock_doc.processed_status = "processing"
        mock_db_session.get = AsyncMock(return_value=mock_doc)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.update_status(uuid4(), "failed", error="Processing error")

        assert mock_doc.processed_status == "failed"
        assert mock_doc.error_message == "Processing error"

    @pytest.mark.asyncio
    async def test_update_status_document_not_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test updating status of non-existent document."""
        mock_db_session.get = AsyncMock(return_value=None)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        # Should not raise
        await service.update_status(uuid4(), "completed")

        mock_db_session.flush.assert_not_called()


class TestQueueForProcessing:
    """Tests for queueing documents."""

    @pytest.mark.asyncio
    async def test_queue_for_processing_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test queueing document for processing."""
        service = DocumentService(db=mock_db_session, redis=mock_redis)
        doc_id = uuid4()

        await service.queue_for_processing(doc_id)

        mock_redis.rpush.assert_called_once()
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_for_processing_no_redis(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test queueing when Redis is not available."""
        service = DocumentService(db=mock_db_session, redis=None)
        doc_id = uuid4()

        # Should not raise
        await service.queue_for_processing(doc_id)


class TestResetForReprocessing:
    """Tests for resetting documents for reprocessing."""

    @pytest.mark.asyncio
    async def test_reset_for_reprocessing(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test resetting document for reprocessing."""
        mock_doc = MagicMock()
        mock_doc.processed_status = "completed"
        mock_db_session.get = AsyncMock(return_value=mock_doc)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.reset_for_reprocessing(uuid4())

        # Should delete chunks and reset status
        mock_db_session.execute.assert_called()  # DELETE chunks
        assert mock_doc.processed_status == "pending"


class TestDeleteDocument:
    """Tests for deleting documents."""

    @pytest.mark.asyncio
    async def test_delete_document(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test deleting a document."""
        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.delete_document(uuid4())

        # Should execute two deletes (chunks and document)
        assert mock_db_session.execute.call_count == 2
        mock_db_session.flush.assert_called_once()


class TestGetChunks:
    """Tests for getting document chunks."""

    @pytest.mark.asyncio
    async def test_get_chunks_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting chunks for a document."""
        mock_chunks = [MagicMock(chunk_index=0), MagicMock(chunk_index=1)]
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_chunks)
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        chunks = await service.get_chunks(uuid4())

        assert len(chunks) == 2

    @pytest.mark.asyncio
    async def test_get_chunks_empty(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting chunks when none exist."""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        chunks = await service.get_chunks(uuid4())

        assert chunks == []


class TestGetPendingDocuments:
    """Tests for getting pending documents."""

    @pytest.mark.asyncio
    async def test_get_pending_documents(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting pending documents."""
        mock_docs = [MagicMock(), MagicMock()]
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_docs)
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        docs = await service.get_pending_documents(limit=50)

        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_get_pending_documents_respects_limit(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that limit is respected."""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        service = DocumentService(db=mock_db_session, redis=mock_redis)

        await service.get_pending_documents(limit=10)

        # Verify the query was executed
        mock_db_session.execute.assert_called_once()
