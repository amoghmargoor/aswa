"""Tests for main application module."""

import pytest
from fastapi.testclient import TestClient

from aswa_ingestion.main import app


class TestAppStartup:
    """Tests for application startup and configuration."""

    def test_app_exists(self) -> None:
        """Test that FastAPI app is created."""
        assert app is not None
        assert app.title == "ASWA Ingestion Service"

    def test_app_has_routes(self) -> None:
        """Test that app has registered routes."""
        routes = [route.path for route in app.routes]
        assert "/health" in routes or any("/health" in r for r in routes)

    def test_app_openapi_schema(self, test_client: TestClient) -> None:
        """Test OpenAPI schema is available."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "ASWA Ingestion Service"
        assert "paths" in schema


class TestAppRouters:
    """Tests for router registration."""

    def test_health_router_mounted(self) -> None:
        """Test health router is mounted."""
        routes = [route.path for route in app.routes]
        assert any("health" in r for r in routes)

    def test_api_prefix(self) -> None:
        """Test API routes have correct prefix."""
        routes = [route.path for route in app.routes]
        api_routes = [r for r in routes if r.startswith("/api/")]
        assert len(api_routes) > 0


class TestExceptionHandlers:
    """Tests for exception handlers."""

    def test_not_found_returns_404(self, test_client: TestClient) -> None:
        """Test that non-existent routes return 404."""
        response = test_client.get("/nonexistent/route")
        assert response.status_code == 404

    def test_method_not_allowed(self, test_client: TestClient) -> None:
        """Test that wrong methods return 405."""
        response = test_client.delete("/health")
        assert response.status_code == 405
