"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MockLLMClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health(self, test_client: TestClient) -> None:
        """Test liveness endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aswa-insight-engine"

    def test_health_live(self, test_client: TestClient) -> None:
        """Test live endpoint."""
        response = test_client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_health_ready(self, test_client: TestClient) -> None:
        """Test readiness endpoint."""
        response = test_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_ready_with_healthy_llm(
        self, test_client: TestClient, mock_llm_client: MockLLMClient
    ) -> None:
        """Test readiness with healthy LLM."""
        response = test_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["checks"]["llm"]["status"] == "healthy"
