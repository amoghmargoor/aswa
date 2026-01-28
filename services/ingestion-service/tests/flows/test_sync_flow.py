"""Tests for sync flow."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.flows.conftest import (
    TEST_TENANT_ID,
    TEST_DATA_SOURCE_ID,
    MockDataSource,
    MockDocument,
)


class TestFetchDataSourceTask:
    """Tests for fetch_data_source task."""

    @pytest.mark.asyncio
    async def test_fetch_data_source_success(
        self, mock_session: AsyncMock, mock_data_source: MockDataSource
    ) -> None:
        """Test successful data source fetch."""
        from aswa_ingestion.flows.sync_flow import fetch_data_source

        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_data_source
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            result = await fetch_data_source.fn(TEST_DATA_SOURCE_ID, TEST_TENANT_ID)

            assert result["id"] == str(TEST_DATA_SOURCE_ID)
            assert result["source_type"] == "gmail"
            assert result["config"] is not None

    @pytest.mark.asyncio
    async def test_fetch_data_source_not_found(
        self, mock_session: AsyncMock
    ) -> None:
        """Test data source not found raises error."""
        from aswa_ingestion.flows.sync_flow import fetch_data_source

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with pytest.raises(ValueError, match="not found"):
                await fetch_data_source.fn(uuid4(), TEST_TENANT_ID)


class TestCreateConnectorTask:
    """Tests for create_connector task."""

    @pytest.mark.asyncio
    async def test_create_connector_success(self) -> None:
        """Test successful connector creation."""
        from aswa_ingestion.flows.sync_flow import create_connector

        data_source = {
            "id": str(TEST_DATA_SOURCE_ID),
            "source_type": "gmail",
            "config": {"credentials": {"access_token": "token"}},
        }

        # Will use mock connector since ConnectorFactory not available
        result = await create_connector.fn(data_source, TEST_TENANT_ID)

        assert result is not None
        assert await result.authenticate() is True


class TestSyncDocumentsTask:
    """Tests for sync_documents task."""

    @pytest.mark.asyncio
    async def test_sync_documents_empty(
        self, mock_session: AsyncMock, mock_connector: AsyncMock
    ) -> None:
        """Test sync with no documents."""
        from aswa_ingestion.flows.sync_flow import sync_documents

        data_source = {
            "id": str(TEST_DATA_SOURCE_ID),
            "sync_cursor": None,
        }

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            result = await sync_documents.fn(
                mock_connector, data_source, TEST_TENANT_ID
            )

            assert result["stats"]["documents_fetched"] == 0
            assert result["stats"]["errors"] == 0


class TestUpdateSyncStatusTask:
    """Tests for update_sync_status task."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_session: AsyncMock) -> None:
        """Test updating sync status."""
        from aswa_ingestion.flows.sync_flow import update_sync_status

        result = {"stats": {"documents_created": 5}, "cursor": {"page": 2}}

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            await update_sync_status.fn(
                TEST_DATA_SOURCE_ID, TEST_TENANT_ID, result
            )

            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_error(self, mock_session: AsyncMock) -> None:
        """Test updating sync status with error."""
        from aswa_ingestion.flows.sync_flow import update_sync_status

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            await update_sync_status.fn(
                TEST_DATA_SOURCE_ID, TEST_TENANT_ID, None, "Connection failed"
            )

            mock_session.execute.assert_called_once()


class TestQueueDocumentsTask:
    """Tests for queue_documents_for_processing task."""

    @pytest.mark.asyncio
    async def test_queue_documents_empty(self, mock_session: AsyncMock) -> None:
        """Test queuing when no pending documents."""
        from aswa_ingestion.flows.sync_flow import queue_documents_for_processing

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            count = await queue_documents_for_processing.fn(TEST_TENANT_ID)

            assert count == 0


class TestSyncDataSourceFlow:
    """Tests for sync_data_source flow."""

    @pytest.mark.asyncio
    async def test_sync_flow_success(
        self,
        mock_session: AsyncMock,
        mock_data_source: MockDataSource,
        mock_connector: AsyncMock,
    ) -> None:
        """Test successful sync flow."""
        from aswa_ingestion.flows.sync_flow import sync_data_source

        # Mock fetch_data_source result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_data_source
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.sync_flow.create_connector"
            ) as mock_create:
                mock_create.fn = AsyncMock(return_value=mock_connector)

                # Run flow - it will use mocks
                result = await sync_data_source(TEST_DATA_SOURCE_ID, TEST_TENANT_ID)

                assert "stats" in result or "documents_queued" in result


class TestScheduledSyncAllFlow:
    """Tests for scheduled_sync_all flow."""

    @pytest.mark.asyncio
    async def test_scheduled_sync_no_sources(self, mock_session: AsyncMock) -> None:
        """Test scheduled sync with no data sources."""
        from aswa_ingestion.flows.sync_flow import scheduled_sync_all

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            results = await scheduled_sync_all()

            assert results["success"] == 0
            assert results["failed"] == 0
            assert results["skipped"] == 0

    @pytest.mark.asyncio
    async def test_scheduled_sync_skips_recent(
        self, mock_session: AsyncMock, mock_data_source: MockDataSource
    ) -> None:
        """Test that recently synced sources are skipped."""
        from aswa_ingestion.flows.sync_flow import scheduled_sync_all

        # Set last sync to 30 minutes ago (less than 60 min frequency)
        mock_data_source.last_sync_at = datetime.utcnow() - timedelta(minutes=30)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_data_source]
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.sync_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            results = await scheduled_sync_all()

            assert results["skipped"] == 1
            assert results["success"] == 0
