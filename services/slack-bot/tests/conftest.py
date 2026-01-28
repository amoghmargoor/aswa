import pytest
from unittest.mock import AsyncMock, MagicMock
from aswa_slack.config import Settings


@pytest.fixture
def settings():
    """Test settings."""
    return Settings(
        slack_bot_token="xoxb-test-token",
        slack_signing_secret="test-secret",
        query_service_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
    )


@pytest.fixture
def mock_query_client():
    """Mock query client."""
    client = MagicMock()
    client.query = AsyncMock(return_value={
        "answer": "Test answer",
        "citations": [],
        "confidence": 0.8,
    })
    client.search = AsyncMock(return_value={"results": []})
    client.get_insights = AsyncMock(return_value={"insights": []})
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_slack_client():
    """Mock Slack client."""
    client = MagicMock()
    client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123.456"})
    client.chat_update = AsyncMock(return_value={"ok": True})
    client.users_info = AsyncMock(return_value={
        "ok": True,
        "user": {"id": "U123", "name": "testuser", "real_name": "Test User"}
    })
    return client


@pytest.fixture
def mock_say():
    """Mock say function."""
    return AsyncMock()


@pytest.fixture
def mock_ack():
    """Mock ack function."""
    return AsyncMock()


@pytest.fixture
def sample_command_body():
    """Sample slash command body."""
    return {
        "team_id": "T123",
        "user_id": "U123",
        "user_name": "testuser",
        "channel_id": "C123",
        "command": "/aswa",
        "text": "What are the risks?",
        "response_url": "https://hooks.slack.com/commands/xxx",
    }


@pytest.fixture
def sample_event_body():
    """Sample event body."""
    return {
        "team_id": "T123",
        "event": {
            "type": "app_mention",
            "user": "U123",
            "text": "<@BOTID> What are the latest insights?",
            "channel": "C123",
            "ts": "123.456",
        }
    }
