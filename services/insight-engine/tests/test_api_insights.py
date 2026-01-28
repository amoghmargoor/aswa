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
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

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
            params={"limit": 5, "offset": 10},
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_get_insight_not_found(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting non-existent insight."""
        response = test_client.get(
            f"/api/v1/insights/{uuid4()}",
            headers=tenant_headers,
        )

        assert response.status_code == 404

    def test_submit_feedback(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test submitting feedback for an insight."""
        insight_id = uuid4()

        response = test_client.post(
            f"/api/v1/insights/{insight_id}/feedback",
            json={
                "rating": 5,
                "is_accurate": True,
                "comment": "Very helpful insight",
            },
            headers=tenant_headers,
        )

        # Will be 404 since insight doesn't exist, but validates endpoint
        assert response.status_code in [200, 404]

    def test_submit_feedback_invalid_rating(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test feedback with invalid rating."""
        response = test_client.post(
            f"/api/v1/insights/{uuid4()}/feedback",
            json={
                "rating": 10,  # Invalid - should be 1-5
                "is_accurate": True,
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
        assert "average_confidence" in data["data"]

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
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "trends" in data["data"]

    def test_get_trends_with_period(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test trends with different periods."""
        for period in ["daily", "weekly", "monthly"]:
            response = test_client.get(
                "/api/v1/insights/trends",
                params={"period": period},
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
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test listing insights."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        result = await service.list_insights(
            tenant_id=TEST_TENANT_ID,
            insight_type=None,
            document_id=None,
            min_confidence=0.0,
            limit=10,
            offset=0,
        )

        assert result is not None
        assert "items" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_insight(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test getting single insight."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        insight = await service.get_insight(uuid4(), TEST_TENANT_ID)

        # Returns None for non-existent insight
        assert insight is None

    @pytest.mark.asyncio
    async def test_submit_feedback(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test submitting feedback."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        # This will fail since insight doesn't exist
        success = await service.submit_feedback(
            insight_id=uuid4(),
            tenant_id=TEST_TENANT_ID,
            user_id=TEST_USER_ID,
            rating=5,
            is_accurate=True,
            comment="Good insight",
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_get_summary(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test getting insights summary."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        summary = await service.get_summary(
            tenant_id=TEST_TENANT_ID,
            start_date=None,
            end_date=None,
        )

        assert summary is not None
        assert "total_insights" in summary
        assert "by_type" in summary
        assert "average_confidence" in summary

    @pytest.mark.asyncio
    async def test_get_trends(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test getting trends."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        trends = await service.get_trends(
            tenant_id=TEST_TENANT_ID,
            period="weekly",
            limit=10,
        )

        assert trends is not None
        assert "trends" in trends

    @pytest.mark.asyncio
    async def test_find_related_insights(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test finding related insights."""
        from aswa_insight.services.insight_service import InsightService

        service = InsightService(mock_session_factory, mock_llm_client)

        # No related insights for non-existent insight
        related = await service.find_related_insights(
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
