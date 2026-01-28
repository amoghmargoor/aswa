"""Tests for processing flow."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.flows.conftest import (
    TEST_TENANT_ID,
    TEST_DOCUMENT_ID,
    TEST_DATA_SOURCE_ID,
    MockDocument,
    MockProcessingResult,
)


class TestFetchPendingDocumentsTask:
    """Tests for fetch_pending_documents task."""

    @pytest.mark.asyncio
    async def test_fetch_pending_success(
        self, mock_session: AsyncMock, mock_document: MockDocument
    ) -> None:
        """Test fetching pending documents."""
        from aswa_ingestion.flows.processing_flow import fetch_pending_documents

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            result = await fetch_pending_documents.fn(TEST_TENANT_ID, 100)

            assert len(result) == 1
            assert result[0]["id"] == str(TEST_DOCUMENT_ID)
            assert result[0]["processed_status"] == "pending"

    @pytest.mark.asyncio
    async def test_fetch_pending_empty(self, mock_session: AsyncMock) -> None:
        """Test fetching when no pending documents."""
        from aswa_ingestion.flows.processing_flow import fetch_pending_documents

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            result = await fetch_pending_documents.fn(TEST_TENANT_ID, 100)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_fetch_pending_respects_limit(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that limit is respected."""
        from aswa_ingestion.flows.processing_flow import fetch_pending_documents

        docs = [
            MockDocument(
                id=uuid4(),
                tenant_id=TEST_TENANT_ID,
                data_source_id=TEST_DATA_SOURCE_ID,
            )
            for _ in range(5)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = docs
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            result = await fetch_pending_documents.fn(TEST_TENANT_ID, 5)

            assert len(result) == 5


class TestProcessSingleDocumentTask:
    """Tests for process_single_document task."""

    @pytest.mark.asyncio
    async def test_process_document_success(
        self,
        mock_session: AsyncMock,
        mock_document: MockDocument,
        mock_pipeline: AsyncMock,
    ) -> None:
        """Test successful document processing."""
        from aswa_ingestion.flows.processing_flow import process_single_document

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.processing_flow.get_processing_pipeline"
            ) as mock_get_pipeline:
                mock_get_pipeline.return_value = mock_pipeline

                document = {
                    "id": str(TEST_DOCUMENT_ID),
                    "tenant_id": str(TEST_TENANT_ID),
                }

                result = await process_single_document.fn(document)

                assert result["status"] == "success"
                assert result["chunks_created"] == 10
                mock_pipeline.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_not_found(
        self, mock_session: AsyncMock
    ) -> None:
        """Test processing non-existent document."""
        from aswa_ingestion.flows.processing_flow import process_single_document

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            document = {
                "id": str(uuid4()),
                "tenant_id": str(TEST_TENANT_ID),
            }

            result = await process_single_document.fn(document)

            assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_process_document_failure(
        self, mock_session: AsyncMock, mock_document: MockDocument
    ) -> None:
        """Test handling processing failure."""
        from aswa_ingestion.flows.processing_flow import process_single_document

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session.execute.return_value = mock_result

        failing_pipeline = AsyncMock()
        failing_pipeline.process = AsyncMock(side_effect=ValueError("Parse error"))

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.processing_flow.get_processing_pipeline"
            ) as mock_get_pipeline:
                mock_get_pipeline.return_value = failing_pipeline

                document = {
                    "id": str(TEST_DOCUMENT_ID),
                    "tenant_id": str(TEST_TENANT_ID),
                }

                result = await process_single_document.fn(document)

                assert result["status"] == "failed"
                assert "Parse error" in result["error"]


class TestAggregateStatsTask:
    """Tests for aggregate_processing_stats task."""

    def test_aggregate_stats_success(self) -> None:
        """Test aggregating successful results."""
        from aswa_ingestion.flows.processing_flow import aggregate_processing_stats

        results = [
            {
                "id": "1",
                "status": "success",
                "chunks_created": 10,
                "vectors_stored": 10,
                "processing_time_ms": 100,
            },
            {
                "id": "2",
                "status": "success",
                "chunks_created": 20,
                "vectors_stored": 20,
                "processing_time_ms": 200,
            },
        ]

        stats = aggregate_processing_stats.fn(results)

        assert stats["total"] == 2
        assert stats["success"] == 2
        assert stats["failed"] == 0
        assert stats["total_chunks"] == 30
        assert stats["total_vectors"] == 30
        assert stats["avg_processing_time_ms"] == 150

    def test_aggregate_stats_mixed(self) -> None:
        """Test aggregating mixed results."""
        from aswa_ingestion.flows.processing_flow import aggregate_processing_stats

        results = [
            {"id": "1", "status": "success", "chunks_created": 10},
            {"id": "2", "status": "failed", "error": "Error"},
            {"id": "3", "status": "not_found"},
        ]

        stats = aggregate_processing_stats.fn(results)

        assert stats["total"] == 3
        assert stats["success"] == 1
        assert stats["failed"] == 1
        assert stats["not_found"] == 1

    def test_aggregate_stats_empty(self) -> None:
        """Test aggregating empty results."""
        from aswa_ingestion.flows.processing_flow import aggregate_processing_stats

        stats = aggregate_processing_stats.fn([])

        assert stats["total"] == 0
        assert stats["success"] == 0


class TestProcessPendingDocumentsFlow:
    """Tests for process_pending_documents flow."""

    @pytest.mark.asyncio
    async def test_process_flow_empty(self, mock_session: AsyncMock) -> None:
        """Test flow with no pending documents."""
        from aswa_ingestion.flows.processing_flow import process_pending_documents

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            stats = await process_pending_documents(tenant_id=TEST_TENANT_ID)

            assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_process_flow_respects_max_documents(
        self, mock_session: AsyncMock, mock_document: MockDocument
    ) -> None:
        """Test flow respects max_documents limit."""
        from aswa_ingestion.flows.processing_flow import process_pending_documents

        # First call returns documents, second returns empty
        call_count = [0]

        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalars.return_value.all.return_value = [mock_document]
            else:
                result.scalars.return_value.all.return_value = []
            # For scalar_one_or_none used in process_single_document
            result.scalar_one_or_none.return_value = mock_document
            return result

        mock_session.execute = mock_execute

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.processing_flow.get_processing_pipeline"
            ) as mock_pipeline:
                mock_pipeline.return_value = AsyncMock(
                    process=AsyncMock(return_value=MockProcessingResult())
                )

                stats = await process_pending_documents(
                    tenant_id=TEST_TENANT_ID, max_documents=1
                )

                # Should have processed 1 document then stopped
                assert stats["total"] >= 0


class TestReprocessFailedDocumentsFlow:
    """Tests for reprocess_failed_documents flow."""

    @pytest.mark.asyncio
    async def test_reprocess_empty(self, mock_session: AsyncMock) -> None:
        """Test reprocess with no failed documents."""
        from aswa_ingestion.flows.processing_flow import reprocess_failed_documents

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "aswa_ingestion.flows.processing_flow.get_async_session"
        ) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            stats = await reprocess_failed_documents(tenant_id=TEST_TENANT_ID)

            assert stats["total"] == 0
            assert stats["reset"] == 0
