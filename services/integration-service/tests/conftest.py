import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    redis.rename = AsyncMock()
    redis.close = AsyncMock()
    return redis


@pytest.fixture
def mock_credentials():
    """Sample credentials for testing."""
    return {
        "email": "test@example.com",
        "api_token": "test-token",
    }


@pytest.fixture
def mock_jira_config():
    """Sample Jira configuration."""
    return {
        "base_url": "https://test.atlassian.net",
        "project_key": "TEST",
    }
