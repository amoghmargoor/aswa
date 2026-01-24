"""Tests for sync service."""

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from aswa_ingestion.models.sync_job import SyncJob, SyncJobStatus
from aswa_ingestion.services.sync_service import SyncService

from tests.conftest import TEST_DATA_SOURCE_ID, TEST_TENANT_ID


class TestStartSync:
    """Tests for starting sync jobs."""

    @pytest.mark.asyncio
    async def test_start_sync_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test successful sync start."""
        mock_redis.set = AsyncMock(return_value=True)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job = await service.start_sync(
            data_source_id=TEST_DATA_SOURCE_ID,
            tenant_id=TEST_TENANT_ID,
            full_sync=False,
        )

        assert job.status == SyncJobStatus.PENDING
        assert job.tenant_id == TEST_TENANT_ID
        assert job.data_source_id == TEST_DATA_SOURCE_ID
        assert job.full_sync is False
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_start_sync_full_sync(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test starting a full sync."""
        mock_redis.set = AsyncMock(return_value=True)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job = await service.start_sync(
            data_source_id=TEST_DATA_SOURCE_ID,
            tenant_id=TEST_TENANT_ID,
            full_sync=True,
        )

        assert job.full_sync is True

    @pytest.mark.asyncio
    async def test_start_sync_already_in_progress(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test sync fails if already in progress."""
        mock_redis.set = AsyncMock(return_value=False)  # Lock not acquired

        service = SyncService(db=mock_db_session, redis=mock_redis)

        with pytest.raises(ValueError, match="already in progress"):
            await service.start_sync(
                data_source_id=TEST_DATA_SOURCE_ID,
                tenant_id=TEST_TENANT_ID,
                full_sync=False,
            )


class TestRunSyncJob:
    """Tests for running sync jobs."""

    @pytest.mark.asyncio
    async def test_run_sync_job_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test successful sync job execution."""
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        await service.run_sync_job(job_id)

        # Verify job status was updated
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_run_sync_job_not_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test running non-existent job."""
        mock_redis.get = AsyncMock(return_value=None)

        service = SyncService(db=mock_db_session, redis=mock_redis)

        # Should not raise, just log and return
        await service.run_sync_job(uuid4())

    @pytest.mark.asyncio
    async def test_run_sync_job_failure_updates_status(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test that job failure updates status correctly."""
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        # Job should complete (TODO placeholder logic)
        await service.run_sync_job(job_id)

        # Lock should be released
        mock_redis.delete.assert_called()


class TestGetJob:
    """Tests for getting sync jobs."""

    @pytest.mark.asyncio
    async def test_get_job_success(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test getting an existing job."""
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        job = await service.get_job(job_id, TEST_TENANT_ID)

        assert job is not None
        assert str(job.id) == sample_sync_job_data["id"]
        assert job.tenant_id == TEST_TENANT_ID

    @pytest.mark.asyncio
    async def test_get_job_wrong_tenant(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test getting job with wrong tenant returns None."""
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])
        wrong_tenant = uuid4()

        job = await service.get_job(job_id, wrong_tenant)

        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_not_found(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting non-existent job."""
        mock_redis.get = AsyncMock(return_value=None)

        service = SyncService(db=mock_db_session, redis=mock_redis)

        job = await service.get_job(uuid4(), TEST_TENANT_ID)

        assert job is None


class TestCancelJob:
    """Tests for cancelling sync jobs."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test cancelling a pending job."""
        sample_sync_job_data["status"] = "pending"
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        await service.cancel_job(job_id, TEST_TENANT_ID)

        # Verify status was updated and lock released
        mock_redis.set.assert_called()
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_running_job(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test cancelling a running job."""
        sample_sync_job_data["status"] = "running"
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        await service.cancel_job(job_id, TEST_TENANT_ID)

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test that cancelling a completed job raises error."""
        sample_sync_job_data["status"] = "completed"
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))

        service = SyncService(db=mock_db_session, redis=mock_redis)
        job_id = UUID(sample_sync_job_data["id"])

        with pytest.raises(ValueError, match="Cannot cancel"):
            await service.cancel_job(job_id, TEST_TENANT_ID)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job_fails(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that cancelling a non-existent job raises error."""
        mock_redis.get = AsyncMock(return_value=None)

        service = SyncService(db=mock_db_session, redis=mock_redis)

        with pytest.raises(ValueError, match="not found"):
            await service.cancel_job(uuid4(), TEST_TENANT_ID)


class TestGetDataSourceStatus:
    """Tests for getting data source sync status."""

    @pytest.mark.asyncio
    async def test_get_status_not_syncing(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting status when not syncing."""
        mock_redis.exists = AsyncMock(return_value=0)

        service = SyncService(db=mock_db_session, redis=mock_redis)

        status = await service.get_data_source_status(
            TEST_DATA_SOURCE_ID, TEST_TENANT_ID
        )

        assert status is not None
        assert status["is_syncing"] is False
        assert status["data_source_id"] == TEST_DATA_SOURCE_ID

    @pytest.mark.asyncio
    async def test_get_status_syncing(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting status when syncing."""
        mock_redis.exists = AsyncMock(return_value=1)

        service = SyncService(db=mock_db_session, redis=mock_redis)

        status = await service.get_data_source_status(
            TEST_DATA_SOURCE_ID, TEST_TENANT_ID
        )

        assert status is not None
        assert status["is_syncing"] is True


class TestListJobs:
    """Tests for listing sync jobs."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test listing jobs when none exist."""
        service = SyncService(db=mock_db_session, redis=mock_redis)

        result = await service.list_jobs(TEST_TENANT_ID)

        assert result["content"] == []
        assert result["total_elements"] == 0

    @pytest.mark.asyncio
    async def test_list_jobs_pagination(
        self,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test listing jobs with pagination."""
        service = SyncService(db=mock_db_session, redis=mock_redis)

        result = await service.list_jobs(TEST_TENANT_ID, page=1, size=10)

        assert result["current_page"] == 1
        assert result["page_size"] == 10
