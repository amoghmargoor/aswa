"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_liveness_check(self, test_client: TestClient) -> None:
        """Test liveness endpoint returns ok."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    def test_readiness_check_healthy(
        self,
        test_client: TestClient,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test readiness endpoint when all dependencies are healthy."""
        # Mock successful health checks
        mock_db_session.execute = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data

    def test_readiness_check_database_unhealthy(
        self,
        test_client: TestClient,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test readiness endpoint when database is unhealthy."""
        # Mock database failure
        mock_db_session.execute = AsyncMock(side_effect=Exception("DB connection failed"))
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/health/ready")
        # Should still return 200 but with unhealthy status in checks
        assert response.status_code in [200, 503]

    def test_readiness_check_redis_unhealthy(
        self,
        test_client: TestClient,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test readiness endpoint when Redis is unhealthy."""
        # Mock Redis failure
        mock_db_session.execute = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis connection failed"))

        response = test_client.get("/health/ready")
        # Should still return 200 but with unhealthy status in checks
        assert response.status_code in [200, 503]


class TestHealthResponseFormat:
    """Tests for health response format."""

    def test_health_response_structure(self, test_client: TestClient) -> None:
        """Test health response has correct structure."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data

    def test_readiness_response_structure(
        self,
        test_client: TestClient,
        mock_db_session: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test readiness response has correct structure."""
        mock_db_session.execute = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)
