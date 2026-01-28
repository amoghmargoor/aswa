"""Test fixtures for Prefect flow testing."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from prefect.testing.utilities import prefect_test_harness


TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")
TEST_DATA_SOURCE_ID = UUID("87654321-4321-4321-4321-cba987654321")
TEST_DOCUMENT_ID = UUID("abcdef12-3456-7890-abcd-ef1234567890")


@pytest.fixture(scope="session", autouse=True)
def prefect_test_fixture():
    """Enable Prefect test mode for all tests."""
    with prefect_test_harness():
        yield


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@dataclass
class MockDataSource:
    """Mock data source for testing."""

    id: UUID
    tenant_id: UUID
    source_type: str = "gmail"
    name: str = "Test Gmail"
    config: dict = None
    sync_cursor: str | None = None
    sync_frequency_minutes: int = 60
    status: str = "active"
    last_sync_at: datetime | None = None

    def __post_init__(self):
        if self.config is None:
            self.config = {"credentials": {"access_token": "test-token"}}


@dataclass
class MockDocument:
    """Mock document for testing."""

    id: UUID
    tenant_id: UUID
    data_source_id: UUID
    external_id: str = "ext-123"
    title: str = "Test Document"
    content_type: str = "application/pdf"
    version_hash: str = "abc123"
    processed_status: str = "pending"
    blob_path: str = "/blobs/test.pdf"
    created_at: datetime = None
    chunk_count: int = 0

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class MockAlert:
    """Mock alert configuration for testing."""

    id: UUID
    tenant_id: UUID
    name: str = "Test Alert"
    pattern_query: str = "security breach"
    conditions: dict = None
    notification_channels: dict = None
    frequency: str = "hourly"
    status: str = "active"
    last_triggered_at: datetime | None = None
    trigger_count: int = 0

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = {"min_severity": "medium"}
        if self.notification_channels is None:
            self.notification_channels = {
                "slack": {"webhook_url": "https://hooks.slack.com/test"}
            }


@dataclass
class MockProcessingResult:
    """Mock processing result."""

    chunks_created: int = 10
    vectors_stored: int = 10
    processing_time_ms: int = 100


@pytest.fixture
def mock_data_source() -> MockDataSource:
    """Create mock data source."""
    return MockDataSource(
        id=TEST_DATA_SOURCE_ID,
        tenant_id=TEST_TENANT_ID,
    )


@pytest.fixture
def mock_document() -> MockDocument:
    """Create mock document."""
    return MockDocument(
        id=TEST_DOCUMENT_ID,
        tenant_id=TEST_TENANT_ID,
        data_source_id=TEST_DATA_SOURCE_ID,
    )


@pytest.fixture
def mock_alert() -> MockAlert:
    """Create mock alert."""
    return MockAlert(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_session_context(mock_session: AsyncMock):
    """Create mock session context manager."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    return mock_get_session


@pytest.fixture
def mock_connector() -> AsyncMock:
    """Create mock connector."""
    connector = AsyncMock()
    connector.authenticate = AsyncMock(return_value=True)

    async def mock_fetch(*args, **kwargs):
        yield [], None

    connector.fetch_documents = mock_fetch
    return connector


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    """Create mock processing pipeline."""
    pipeline = AsyncMock()
    pipeline.process = AsyncMock(return_value=MockProcessingResult())
    return pipeline


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Create mock embedder."""
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)
    return embedder
