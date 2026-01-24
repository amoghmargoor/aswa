"""Tests for sync API endpoints."""

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_DATA_SOURCE_ID, TEST_TENANT_ID


class TestSyncTrigger:
    """Tests for sync trigger endpoint."""

    def test_trigger_sync_success(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test successful sync trigger."""
        # Mock lock acquisition
        mock_redis.set = AsyncMock(return_value=True)

        response = test_client.post(
            f"/api/v1/data-sources/{TEST_DATA_SOURCE_ID}/sync",
            json={"full_sync": False},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_trigger_sync_already_in_progress(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
    ) -> None:
        """Test sync trigger when sync is already in progress."""
        # Mock lock already exists
        mock_redis.set = AsyncMock(return_value=False)

        response = test_client.post(
            f"/api/v1/data-sources/{TEST_DATA_SOURCE_ID}/sync",
            json={"full_sync": False},
        )
        assert response.status_code == 409
        data = response.json()
        assert "already in progress" in data["detail"].lower()

    def test_trigger_full_sync(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
    ) -> None:
        """Test triggering a full sync."""
        mock_redis.set = AsyncMock(return_value=True)

        response = test_client.post(
            f"/api/v1/data-sources/{TEST_DATA_SOURCE_ID}/sync",
            json={"full_sync": True},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["full_sync"] is True

    def test_trigger_sync_invalid_uuid(self, test_client: TestClient) -> None:
        """Test sync trigger with invalid UUID."""
        response = test_client.post(
            "/api/v1/data-sources/invalid-uuid/sync",
            json={"full_sync": False},
        )
        assert response.status_code == 422


class TestSyncStatus:
    """Tests for sync status endpoints."""

    def test_get_data_source_status(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting data source sync status."""
        mock_redis.exists = AsyncMock(return_value=0)

        response = test_client.get(
            f"/api/v1/data-sources/{TEST_DATA_SOURCE_ID}/sync/status"
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_syncing" in data
        assert data["is_syncing"] is False

    def test_get_data_source_status_syncing(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting data source status when syncing."""
        mock_redis.exists = AsyncMock(return_value=1)

        response = test_client.get(
            f"/api/v1/data-sources/{TEST_DATA_SOURCE_ID}/sync/status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_syncing"] is True


class TestSyncJobEndpoints:
    """Tests for sync job management endpoints."""

    def test_list_sync_jobs(self, test_client: TestClient) -> None:
        """Test listing sync jobs."""
        response = test_client.get("/api/v1/sync-jobs")
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "total_elements" in data
        assert isinstance(data["content"], list)

    def test_list_sync_jobs_with_filters(self, test_client: TestClient) -> None:
        """Test listing sync jobs with filters."""
        response = test_client.get(
            "/api/v1/sync-jobs",
            params={
                "data_source_id": str(TEST_DATA_SOURCE_ID),
                "status": "completed",
                "page": 0,
                "size": 10,
            },
        )
        assert response.status_code == 200

    def test_get_sync_job(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test getting a specific sync job."""
        job_id = sample_sync_job_data["id"]
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))

        response = test_client.get(f"/api/v1/sync-jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    def test_get_sync_job_not_found(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting non-existent sync job."""
        mock_redis.get = AsyncMock(return_value=None)

        response = test_client.get(f"/api/v1/sync-jobs/{uuid4()}")
        assert response.status_code == 404

    def test_cancel_sync_job(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test cancelling a sync job."""
        sample_sync_job_data["status"] = "running"
        job_id = sample_sync_job_data["id"]
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        response = test_client.post(f"/api/v1/sync-jobs/{job_id}/cancel")
        assert response.status_code == 200

    def test_cancel_completed_job_fails(
        self,
        test_client: TestClient,
        mock_redis: AsyncMock,
        sample_sync_job_data: dict[str, Any],
    ) -> None:
        """Test that cancelling a completed job fails."""
        sample_sync_job_data["status"] = "completed"
        job_id = sample_sync_job_data["id"]
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_sync_job_data))

        response = test_client.post(f"/api/v1/sync-jobs/{job_id}/cancel")
        assert response.status_code == 400
