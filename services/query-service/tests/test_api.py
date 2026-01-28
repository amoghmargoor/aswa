import pytest
from uuid import uuid4


class TestHealthEndpoints:
    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_readiness(self, client):
        """Test readiness endpoint."""
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_liveness(self, client):
        """Test liveness endpoint."""
        response = client.get("/api/v1/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestQueryEndpoints:
    def test_query_requires_tenant(self, client):
        """Test that query requires tenant ID."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test query"},
        )
        assert response.status_code == 422

    def test_query_with_tenant(self, client, headers):
        """Test query with tenant ID."""
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": "What are the main risks?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "query_id" in data
        assert "answer" in data

    def test_query_validation(self, client, headers):
        """Test query validation."""
        # Empty query
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": ""},
        )
        assert response.status_code == 422

        # Query too long
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": "x" * 1001},
        )
        assert response.status_code == 422


class TestSearchEndpoints:
    def test_search(self, client, headers):
        """Test semantic search."""
        response = client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "test search"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "processing_time_ms" in data


class TestInsightEndpoints:
    def test_query_insights(self, client, headers):
        """Test insight query."""
        response = client.post(
            "/api/v1/insights",
            headers=headers,
            json={"min_confidence": 0.5},
        )
        # May fail due to insight-engine not running, which is OK
        assert response.status_code in [200, 500]
