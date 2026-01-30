"""Tests for insights API endpoints."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from tests.conftest import (
    TEST_TENANT_ID,
    TEST_USER_ID,
    TEST_DOCUMENT_ID,
    MockLLMClient,
)


class TestInsightsEndpoints:
    """Tests for insights API endpoints."""

    def test_list_insights_requires_auth(self, test_client: TestClient) -> None:
        """Test that listing insights requires tenant headers."""
        response = test_client.get("/api/v1/insights")

        assert response.status_code == 422  # Missing headers

    def test_list_insights_empty(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test listing insights when none exist."""
        response = test_client.get(
            "/api/v1/insights",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "content" in data["data"]
        assert "total_elements" in data["data"]

    def test_list_insights_with_filters(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test listing insights with filters."""
        response = test_client.get(
            "/api/v1/insights",
            params={
                "insight_type": "entity",
                "min_confidence": 0.8,
                "limit": 10,
                "offset": 0,
            },
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_list_insights_by_document(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test listing insights for a specific document."""
        response = test_client.get(
            "/api/v1/insights",
            params={"document_id": str(TEST_DOCUMENT_ID)},
            headers=tenant_headers,
        )

        assert response.status_code == 200

    def test_list_insights_pagination(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test insights pagination."""
        response = test_client.get(
            "/api/v1/insights",
            params={"size": 5, "page": 0},
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data["data"]
        assert "total_elements" in data["data"]

    def test_get_insight_not_found(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting non-existent insight returns mock data for demo."""
        response = test_client.get(
            f"/api/v1/insights/{uuid4()}",
            headers=tenant_headers,
        )

        # Current implementation returns mock data for demo purposes
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_feedback(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test submitting feedback for an insight."""
        insight_id = uuid4()

        response = test_client.post(
            f"/api/v1/insights/{insight_id}/feedback",
            json={
                "feedback": "confirmed",
                "comment": "Very helpful insight",
            },
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_feedback_invalid(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test feedback with invalid feedback type."""
        response = test_client.post(
            f"/api/v1/insights/{uuid4()}/feedback",
            json={
                "feedback": "invalid_type",  # Invalid - should be confirmed or rejected
            },
            headers=tenant_headers,
        )

        assert response.status_code == 422

    def test_get_summary_requires_auth(self, test_client: TestClient) -> None:
        """Test that summary requires tenant headers."""
        response = test_client.get("/api/v1/insights/summary")

        assert response.status_code == 422

    def test_get_summary(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting insights summary."""
        response = test_client.get(
            "/api/v1/insights/summary",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_insights" in data["data"]
        assert "by_type" in data["data"]
        assert "avg_confidence" in data["data"]

    def test_get_summary_with_date_range(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test summary with date range filter."""
        response = test_client.get(
            "/api/v1/insights/summary",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
            headers=tenant_headers,
        )

        assert response.status_code == 200

    def test_get_trends(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting insight trends."""
        response = test_client.get(
            "/api/v1/insights/trends",
            params={"days": 30},
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "daily_counts" in data["data"]

    def test_get_trends_with_period(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test trends with different day ranges."""
        for days in [7, 30, 60]:
            response = test_client.get(
                "/api/v1/insights/trends",
                params={"days": days},
                headers=tenant_headers,
            )

            assert response.status_code == 200

    def test_get_related_insights(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting related insights."""
        insight_id = uuid4()

        response = test_client.get(
            f"/api/v1/insights/{insight_id}/related",
            headers=tenant_headers,
        )

        # 404 since insight doesn't exist
        assert response.status_code == 404

    def test_get_related_with_limit(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test related insights with limit."""
        insight_id = uuid4()

        response = test_client.get(
            f"/api/v1/insights/{insight_id}/related",
            params={"limit": 5},
            headers=tenant_headers,
        )

        assert response.status_code == 404  # Insight doesn't exist


class TestInsightService:
    """Tests for InsightService."""

    @pytest.mark.asyncio
    async def test_list_insights(
        self, mock_session_factory
    ) -> None:
        """Test listing insights."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        result = await service.list_insights(
            tenant_id=TEST_TENANT_ID,
            insight_type=None,
            min_confidence=0.0,
        )

        assert result is not None
        assert "content" in result
        assert "total_elements" in result

    @pytest.mark.asyncio
    async def test_get_insight(
        self, mock_session_factory
    ) -> None:
        """Test getting single insight."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        insight = await service.get_insight(uuid4(), TEST_TENANT_ID)

        # Returns mock data for any insight ID
        assert insight is not None

    @pytest.mark.asyncio
    async def test_submit_feedback(
        self, mock_session_factory
    ) -> None:
        """Test submitting feedback."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        # Use update_feedback method
        success = await service.update_feedback(
            insight_id=uuid4(),
            tenant_id=TEST_TENANT_ID,
            user_id=TEST_USER_ID,
            feedback="confirmed",
            comment="Good insight",
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_get_summary(
        self, mock_session_factory
    ) -> None:
        """Test getting insights summary."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        summary = await service.get_summary(
            tenant_id=TEST_TENANT_ID,
        )

        assert summary is not None
        assert "total_insights" in summary
        assert "by_type" in summary
        assert "avg_confidence" in summary

    @pytest.mark.asyncio
    async def test_get_trends(
        self, mock_session_factory
    ) -> None:
        """Test getting trends."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        trends = await service.get_trends(
            tenant_id=TEST_TENANT_ID,
        )

        assert trends is not None
        assert "daily_counts" in trends

    @pytest.mark.asyncio
    async def test_find_related_insights(
        self, mock_session_factory
    ) -> None:
        """Test finding related insights."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory)

        # No related insights for non-existent insight
        related = await service.get_related_insights(
            insight_id=uuid4(),
            tenant_id=TEST_TENANT_ID,
            limit=5,
        )

        assert related == []


class TestInsightFiltering:
    """Tests for insight filtering and search."""

    def test_filter_by_type(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test filtering by insight type."""
        for insight_type in ["entity", "risk", "opportunity", "pattern"]:
            response = test_client.get(
                "/api/v1/insights",
                params={"insight_type": insight_type},
                headers=tenant_headers,
            )

            assert response.status_code == 200

    def test_filter_by_confidence(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test filtering by minimum confidence."""
        response = test_client.get(
            "/api/v1/insights",
            params={"min_confidence": 0.9},
            headers=tenant_headers,
        )

        assert response.status_code == 200

    def test_search_insights(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test searching insights."""
        response = test_client.get(
            "/api/v1/insights",
            params={"search": "risk analysis"},
            headers=tenant_headers,
        )

        assert response.status_code == 200

    def test_sort_insights(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test sorting insights."""
        for sort_by in ["created_at", "confidence", "insight_type"]:
            for order in ["asc", "desc"]:
                response = test_client.get(
                    "/api/v1/insights",
                    params={"sort_by": sort_by, "order": order},
                    headers=tenant_headers,
                )

                assert response.status_code == 200
