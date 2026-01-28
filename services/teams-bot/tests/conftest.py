import pytest
from unittest.mock import AsyncMock, MagicMock
from aswa_teams.config import Settings


@pytest.fixture
def settings():
    return Settings(
        app_id="test-app-id",
        app_password="test-password",
        query_service_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
    )


@pytest.fixture
def mock_query_client():
    client = MagicMock()
    client.query = AsyncMock(return_value={
        "answer": "Test answer",
        "citations": [],
        "confidence": 0.8,
        "query_id": "test-123",
    })
    client.get_insights = AsyncMock(return_value={"insights": []})
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_user_service():
    service = MagicMock()
    service.get_or_create_user = AsyncMock()
    service.link_user_to_tenant = AsyncMock()
    return service
