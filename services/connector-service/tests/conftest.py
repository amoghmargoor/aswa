"""Test fixtures for connector service."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_connector.main import app
from aswa_connector.dependencies import (
    get_db_session,
    get_redis,
    get_tenant_context,
    get_provider,
)


TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")
TEST_USER_ID = UUID("87654321-4321-4321-4321-cba987654321")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client."""
    redis = AsyncMock(spec=Redis)
    redis.ping = AsyncMock(return_value=True)
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_provider() -> AsyncMock:
    """Create mock connector provider."""
    provider = AsyncMock()
    provider.name = "airbyte"
    provider.list_available_connectors = AsyncMock(return_value=[])
    provider.get_connector_definition = AsyncMock(return_value=None)
    provider.create_connection = AsyncMock()
    provider.test_airbyte_source = AsyncMock()
    provider.trigger_airbyte_sync = AsyncMock()
    provider.cancel_airbyte_job = AsyncMock()
    return provider


@pytest.fixture
def tenant_context() -> dict[str, Any]:
    """Create test tenant context."""
    return {
        "tenant_id": TEST_TENANT_ID,
        "user_id": TEST_USER_ID,
        "roles": ["user", "admin"],
    }


@pytest.fixture
def test_client(
    mock_db_session: AsyncMock,
    mock_redis: AsyncMock,
    mock_provider: AsyncMock,
    tenant_context: dict[str, Any],
) -> TestClient:
    """Create test client with mocked dependencies."""

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_db_session

    async def override_redis() -> AsyncGenerator[Redis, None]:
        yield mock_redis

    async def override_provider() -> Any:
        return mock_provider

    async def override_tenant() -> dict[str, Any]:
        return tenant_context

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_provider] = override_provider
    app.dependency_overrides[get_tenant_context] = override_tenant

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    app.dependency_overrides.clear()
