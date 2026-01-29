"""Pytest fixtures for Agent Service tests."""

import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from aswa_agents.config import get_settings, Settings
from aswa_agents.persistence.database import get_session


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return Settings(
        environment="development",
        debug=True,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_agents",
    )


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def test_tenant_id() -> str:
    """Get test tenant ID."""
    return f"test-tenant-{uuid4().hex[:8]}"


@pytest.fixture
def auth_headers(test_tenant_id: str, settings: Settings) -> dict:
    """Create authorization headers with valid JWT."""
    from jose import jwt

    token = jwt.encode(
        {"sub": "test-user", "tenant_id": test_tenant_id, "roles": ["admin"]},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app(settings: Settings):
    """Create test application."""
    # Create a minimal test app without importing modules that need extra dependencies
    from fastapi import FastAPI

    test_app = FastAPI()

    @test_app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "agent-service"}

    @test_app.get("/ready")
    async def readiness_check():
        return {"status": "ready"}

    return test_app


@pytest.fixture
def client(app, settings: Settings) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app, settings: Settings) -> AsyncClient:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
