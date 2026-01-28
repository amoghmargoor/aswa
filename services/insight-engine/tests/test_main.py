"""Tests for main app startup."""

import pytest
from fastapi.testclient import TestClient


class TestAppStartup:
    """Tests for application startup."""

    def test_app_creates_successfully(self) -> None:
        """Test that the app can be created."""
        from aswa_insight.main import app

        assert app is not None
        assert app.title == "ASWA Insight Engine"

    def test_app_has_routes(self) -> None:
        """Test that routes are registered."""
        from aswa_insight.main import app

        routes = [route.path for route in app.routes]

        assert "/health" in routes
        assert "/health/ready" in routes
        assert "/metrics" in routes

    def test_api_routes_registered(self) -> None:
        """Test that API routes are registered."""
        from aswa_insight.main import app

        routes = [route.path for route in app.routes]

        # Check extraction routes
        assert "/api/v1/extract" in routes

        # Check insights routes
        assert "/api/v1/insights" in routes
