"""Root pytest configuration for ASWA tests."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Test database URL
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://aswa:aswa@localhost:5433/aswa_test"
)

TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL",
    "redis://localhost:6380"
)

TEST_ELASTICSEARCH_URL = os.environ.get(
    "TEST_ELASTICSEARCH_URL",
    "http://localhost:9201"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create database engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests with rollback."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = MagicMock()
    mock.get = MagicMock(return_value=None)
    mock.set = MagicMock(return_value=True)
    mock.delete = MagicMock(return_value=True)
    mock.expire = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    mock = MagicMock()
    mock.search = MagicMock(return_value={"hits": {"hits": [], "total": {"value": 0}}})
    mock.index = MagicMock(return_value={"result": "created"})
    mock.delete = MagicMock(return_value={"result": "deleted"})
    return mock


@pytest.fixture
def mock_s3():
    """Mock S3 client."""
    mock = MagicMock()
    mock.upload_file = MagicMock(return_value=None)
    mock.download_file = MagicMock(return_value=None)
    mock.delete_object = MagicMock(return_value=None)
    mock.generate_presigned_url = MagicMock(return_value="https://s3.example.com/file")
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    mock = MagicMock()
    mock.complete = MagicMock(return_value={
        "content": "This is a mock LLM response.",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    })
    return mock


@pytest.fixture
def sample_tenant() -> dict:
    """Sample tenant data."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Test Tenant",
        "slug": "test",
        "settings": {"features": ["all"]},
    }


@pytest.fixture
def sample_user(sample_tenant) -> dict:
    """Sample user data."""
    return {
        "id": "00000000-0000-0000-0000-000000000002",
        "tenant_id": sample_tenant["id"],
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
    }


@pytest.fixture
def sample_document(sample_tenant) -> dict:
    """Sample document data."""
    return {
        "id": "00000000-0000-0000-0000-000000000003",
        "tenant_id": sample_tenant["id"],
        "name": "Test Document.pdf",
        "content_type": "application/pdf",
        "size_bytes": 12345,
        "status": "processed",
    }


@pytest.fixture
def sample_insight(sample_tenant, sample_document) -> dict:
    """Sample insight data."""
    return {
        "id": "00000000-0000-0000-0000-000000000004",
        "tenant_id": sample_tenant["id"],
        "document_id": sample_document["id"],
        "type": "risk",
        "category": "financial",
        "title": "Budget Overrun Risk",
        "description": "Analysis indicates potential budget overrun in Q4.",
        "severity": "high",
        "confidence": 0.85,
    }


@pytest.fixture
def auth_headers(sample_tenant, sample_user) -> dict:
    """Authentication headers for testing."""
    import jwt

    token = jwt.encode(
        {
            "sub": sample_user["id"],
            "tenant_id": sample_tenant["id"],
            "email": sample_user["email"],
            "role": sample_user["role"],
        },
        "test-secret",
        algorithm="HS256",
    )

    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": sample_tenant["id"],
    }
