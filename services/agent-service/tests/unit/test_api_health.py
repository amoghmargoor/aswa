"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "agent-service"

    def test_readiness_check(self, client: TestClient):
        """Test /ready endpoint."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
