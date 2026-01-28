"""Test fixtures for document processor worker."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import fakeredis.aioredis

from aswa_processor.queue import RedisQueue
from aswa_processor.worker import Worker


TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")
TEST_DOCUMENT_ID = UUID("87654321-4321-4321-4321-cba987654321")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    """Create fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def redis_queue(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisQueue:
    """Create RedisQueue with fake Redis."""
    queue = RedisQueue(
        redis_client=fake_redis,
        queue_name="test_queue",
        consumer_group="test_group",
        consumer_name="test_consumer",
        dlq_name="test_queue_dlq",
    )
    await queue.initialize()
    return queue


@pytest.fixture
def mock_handler() -> AsyncMock:
    """Create mock job handler."""
    handler = AsyncMock()
    handler.return_value = None
    return handler


@pytest.fixture
async def worker(
    redis_queue: RedisQueue,
    mock_handler: AsyncMock,
) -> Worker:
    """Create Worker with mocked dependencies."""
    return Worker(
        queue=redis_queue,
        handler=mock_handler,
        concurrency=2,
        batch_size=5,
        poll_interval=0.1,
        max_retries=3,
        job_timeout=10.0,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    """Create mock session factory."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    return factory


@dataclass
class MockDocument:
    """Mock document for testing."""

    id: UUID
    tenant_id: UUID
    name: str = "test.pdf"
    content_type: str = "application/pdf"
    processed_status: str = "pending"


@dataclass
class MockProcessingResult:
    """Mock processing result."""

    chunks_created: int = 10
    vectors_stored: int = 10
    processing_time_ms: int = 100


@pytest.fixture
def mock_document() -> MockDocument:
    """Create mock document."""
    return MockDocument(
        id=TEST_DOCUMENT_ID,
        tenant_id=TEST_TENANT_ID,
    )


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    """Create mock processing pipeline."""
    pipeline = AsyncMock()
    pipeline.process = AsyncMock(return_value=MockProcessingResult())
    return pipeline


@pytest.fixture
def mock_repository(mock_document: MockDocument) -> MagicMock:
    """Create mock document repository."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=mock_document)
    repo.update_status = AsyncMock()
    return repo
