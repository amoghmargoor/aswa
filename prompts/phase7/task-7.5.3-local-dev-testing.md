# Task 7.5.3: Local Development - Testing Environment

## Context

You are setting up local development environment for ASWA. Development scripts are complete. Now we need testing environment configurations.

## Objective

Create testing environment configurations that:
1. Support unit testing setup
2. Enable integration testing
3. Configure test fixtures
4. Support test data generation
5. Enable test coverage reporting

## Requirements

### 1. Create `/tests/conftest.py`
```python
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
```

### 2. Create `/tests/factories.py`
```python
"""Test data factories for ASWA."""

import uuid
from datetime import datetime, timedelta
from typing import Any
import random

from faker import Faker

fake = Faker()


class TenantFactory:
    """Factory for creating test tenants."""

    @staticmethod
    def create(**kwargs) -> dict[str, Any]:
        """Create a tenant with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "name": kwargs.get("name", fake.company()),
            "slug": kwargs.get("slug", fake.slug()),
            "settings": kwargs.get("settings", {"features": ["all"]}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }


class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a user with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "email": kwargs.get("email", fake.email()),
            "name": kwargs.get("name", fake.name()),
            "role": kwargs.get("role", "user"),
            "settings": kwargs.get("settings", {}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }


class DocumentFactory:
    """Factory for creating test documents."""

    CONTENT_TYPES = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain",
    }

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a document with default or custom values."""
        doc_type = kwargs.get("doc_type", random.choice(list(DocumentFactory.CONTENT_TYPES.keys())))
        name = kwargs.get("name", f"{fake.catch_phrase()}.{doc_type}")

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "name": name,
            "content_type": kwargs.get("content_type", DocumentFactory.CONTENT_TYPES[doc_type]),
            "size_bytes": kwargs.get("size_bytes", random.randint(1000, 10000000)),
            "storage_path": kwargs.get("storage_path", f"documents/{uuid.uuid4()}/{name}"),
            "status": kwargs.get("status", "pending"),
            "metadata": kwargs.get("metadata", {}),
            "uploaded_by": kwargs.get("uploaded_by"),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
            "processed_at": kwargs.get("processed_at"),
        }

    @staticmethod
    def create_batch(count: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Create multiple documents."""
        return [DocumentFactory.create(tenant_id) for _ in range(count)]


class InsightFactory:
    """Factory for creating test insights."""

    TYPES = ["risk", "opportunity"]
    CATEGORIES = ["financial", "operational", "compliance", "strategic", "technical"]
    SEVERITIES = ["low", "medium", "high", "critical"]

    TITLES = {
        "risk": [
            "Budget overrun risk",
            "Security vulnerability detected",
            "Compliance gap identified",
            "Resource constraint warning",
            "Timeline delay risk",
        ],
        "opportunity": [
            "Cost reduction opportunity",
            "Process optimization potential",
            "Market expansion opportunity",
            "Revenue growth potential",
            "Efficiency improvement possible",
        ],
    }

    @staticmethod
    def create(
        tenant_id: str | None = None,
        document_id: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Create an insight with default or custom values."""
        insight_type = kwargs.get("type", random.choice(InsightFactory.TYPES))
        title = kwargs.get(
            "title",
            random.choice(InsightFactory.TITLES.get(insight_type, InsightFactory.TITLES["risk"]))
        )

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "document_id": document_id or kwargs.get("document_id", str(uuid.uuid4())),
            "type": insight_type,
            "category": kwargs.get("category", random.choice(InsightFactory.CATEGORIES)),
            "title": title,
            "description": kwargs.get("description", fake.paragraph(nb_sentences=3)),
            "severity": kwargs.get("severity", random.choice(InsightFactory.SEVERITIES)),
            "confidence": kwargs.get("confidence", round(random.uniform(0.6, 0.99), 2)),
            "metadata": kwargs.get("metadata", {}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }

    @staticmethod
    def create_batch(
        count: int,
        tenant_id: str | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Create multiple insights."""
        return [InsightFactory.create(tenant_id, document_id) for _ in range(count)]


class QueryFactory:
    """Factory for creating test queries."""

    SAMPLE_QUERIES = [
        "What are the main risks in this document?",
        "Summarize the key findings",
        "What are the budget implications?",
        "List the action items",
        "What compliance issues were identified?",
        "What opportunities are mentioned?",
        "What is the overall assessment?",
    ]

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a query with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "user_id": kwargs.get("user_id", str(uuid.uuid4())),
            "query": kwargs.get("query", random.choice(QueryFactory.SAMPLE_QUERIES)),
            "document_ids": kwargs.get("document_ids", []),
            "response": kwargs.get("response"),
            "citations": kwargs.get("citations", []),
            "tokens_used": kwargs.get("tokens_used", random.randint(100, 2000)),
            "duration_ms": kwargs.get("duration_ms", random.randint(500, 5000)),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
        }
```

### 3. Create `/tests/integration/__init__.py`
```python
"""Integration tests for ASWA services."""
```

### 4. Create `/tests/integration/test_document_flow.py`
```python
"""Integration tests for document processing flow."""

import pytest
import httpx
import asyncio
import os
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://localhost:8000")


@pytest.fixture
def api_client():
    """Create API client."""
    return httpx.AsyncClient(base_url=API_URL, timeout=60.0)


@pytest.fixture
def auth_token():
    """Get authentication token."""
    # In a real test, this would authenticate properly
    return os.environ.get("TEST_API_TOKEN", "test-token")


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF file for testing."""
    # Create a simple text file (in real tests, use a proper PDF)
    file_path = tmp_path / "test-document.txt"
    file_path.write_text("""
    Test Document for ASWA Integration Tests

    This document contains sample content for testing the document
    processing pipeline. It includes:

    1. Risk Assessment
    The project has potential budget overrun risks of approximately
    15% based on current spending patterns.

    2. Opportunities
    There are opportunities for cost optimization in the
    procurement process that could save up to $50,000 annually.

    3. Recommendations
    We recommend implementing automated monitoring and
    establishing quarterly review processes.
    """)
    return file_path


class TestDocumentProcessingFlow:
    """Test the complete document processing flow."""

    @pytest.mark.asyncio
    async def test_upload_and_process_document(self, api_client, auth_token, sample_pdf):
        """Test uploading and processing a document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload document
        with open(sample_pdf, "rb") as f:
            response = await api_client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("test-document.txt", f, "text/plain")},
            )

        assert response.status_code == 201
        document = response.json()
        assert "id" in document
        document_id = document["id"]

        # Wait for processing
        max_retries = 30
        for _ in range(max_retries):
            response = await api_client.get(
                f"/api/v1/documents/{document_id}",
                headers=headers,
            )
            assert response.status_code == 200

            doc = response.json()
            if doc["status"] == "processed":
                break
            elif doc["status"] == "failed":
                pytest.fail(f"Document processing failed: {doc.get('error')}")

            await asyncio.sleep(2)
        else:
            pytest.fail("Document processing timed out")

        # Verify insights were generated
        response = await api_client.get(
            f"/api/v1/documents/{document_id}/insights",
            headers=headers,
        )
        assert response.status_code == 200
        insights = response.json()
        assert len(insights["items"]) > 0

    @pytest.mark.asyncio
    async def test_query_processed_document(self, api_client, auth_token, sample_pdf):
        """Test querying a processed document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload and wait for processing
        with open(sample_pdf, "rb") as f:
            response = await api_client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("test-document.txt", f, "text/plain")},
            )

        document_id = response.json()["id"]

        # Wait for processing
        await asyncio.sleep(10)

        # Query the document
        response = await api_client.post(
            "/api/v1/query",
            headers=headers,
            json={
                "query": "What risks are mentioned?",
                "document_ids": [document_id],
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert "response" in result
        assert len(result["response"]) > 0


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, api_client):
        """Test health check endpoint."""
        response = await api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_documents(self, api_client, auth_token):
        """Test listing documents."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await api_client.get(
            "/api/v1/documents",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_insights(self, api_client, auth_token):
        """Test listing insights."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await api_client.get(
            "/api/v1/insights",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, api_client):
        """Test that unauthorized access is rejected."""
        response = await api_client.get("/api/v1/documents")
        assert response.status_code == 401
```

### 5. Create `/tests/pytest.ini`
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### 6. Create `/tests/requirements.txt`
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-xdist>=3.3.0
pytest-timeout>=2.2.0
pytest-html>=4.0.0
httpx>=0.25.0
faker>=19.0.0
factory-boy>=3.3.0
aiosqlite>=0.19.0
```

## Verification

1. Install test dependencies: `pip install -r tests/requirements.txt`
2. Start test containers: `docker-compose -f infrastructure/docker/docker-compose.test.yaml up -d`
3. Run unit tests: `pytest tests/ -v --ignore=tests/integration`
4. Run integration tests: `pytest tests/integration/ -v`
5. Generate coverage report: `pytest tests/ --cov=services --cov-report=html`
