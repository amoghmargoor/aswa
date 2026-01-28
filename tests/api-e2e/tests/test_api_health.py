import pytest
import httpx
import os

API_URL = os.environ.get("API_URL", "http://localhost:8000")


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_api_gateway_health(self):
        """Test API gateway health endpoint."""
        response = httpx.get(f"{API_URL}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_gateway_ready(self):
        """Test API gateway readiness endpoint."""
        response = httpx.get(f"{API_URL}/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    def test_api_gateway_metrics(self):
        """Test API gateway metrics endpoint."""
        response = httpx.get(f"{API_URL}/metrics")

        assert response.status_code == 200
        assert "http_requests_total" in response.text


class TestAPIEndpoints:
    """Test API endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers."""
        token = os.environ.get("API_TOKEN")
        return {"Authorization": f"Bearer {token}"}

    def test_get_documents(self, auth_headers):
        """Test get documents endpoint."""
        response = httpx.get(
            f"{API_URL}/api/v1/documents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_get_insights(self, auth_headers):
        """Test get insights endpoint."""
        response = httpx.get(
            f"{API_URL}/api/v1/insights",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_submit_query(self, auth_headers):
        """Test query submission endpoint."""
        response = httpx.post(
            f"{API_URL}/api/v1/query",
            headers=auth_headers,
            json={
                "query": "What are the main topics in the documents?",
            },
            timeout=120.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_unauthorized_access(self):
        """Test unauthorized access is rejected."""
        response = httpx.get(f"{API_URL}/api/v1/documents")

        assert response.status_code == 401

    def test_rate_limiting(self, auth_headers):
        """Test rate limiting is enforced."""
        # Make many requests quickly
        for _ in range(150):
            httpx.get(
                f"{API_URL}/api/v1/documents",
                headers=auth_headers,
            )

        # Should get rate limited
        response = httpx.get(
            f"{API_URL}/api/v1/documents",
            headers=auth_headers,
        )

        assert response.status_code == 429
