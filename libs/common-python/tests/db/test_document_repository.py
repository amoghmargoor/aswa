"""Tests for document repository specialized queries."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models import DataSource, Document
from aswa_common.db.repositories.document_repository import DocumentRepository
from aswa_common.models import PageRequest


@pytest.fixture
async def data_source(session: AsyncSession, tenant) -> DataSource:
    """Create test data source."""
    data_source = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Test Source",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add(data_source)
    await session.flush()
    await session.refresh(data_source)
    return data_source


@pytest.mark.asyncio
async def test_find_by_hash(session: AsyncSession, tenant, data_source):
    """Test finding document by content hash."""
    repo = DocumentRepository(session, tenant.id)

    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-1",
        title="Test Doc",
        content="Content",
        content_type="text/plain",
        content_hash="abc123hash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo.create(doc)

    found = await repo.find_by_hash("abc123hash")

    assert found is not None
    assert found.id == doc.id
    assert found.content_hash == "abc123hash"


@pytest.mark.asyncio
async def test_find_by_hash_not_found(session: AsyncSession, tenant):
    """Test finding document by non-existent hash returns None."""
    repo = DocumentRepository(session, tenant.id)

    found = await repo.find_by_hash("nonexistent")

    assert found is None


@pytest.mark.asyncio
async def test_find_by_external_id(session: AsyncSession, tenant, data_source):
    """Test finding document by data source and external ID."""
    repo = DocumentRepository(session, tenant.id)

    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="ext-123",
        title="External Doc",
        content="Content",
        content_type="text/plain",
        content_hash="def456",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo.create(doc)

    found = await repo.find_by_external_id(data_source.id, "ext-123")

    assert found is not None
    assert found.id == doc.id
    assert found.external_id == "ext-123"


@pytest.mark.asyncio
async def test_find_by_external_id_not_found(session: AsyncSession, tenant, data_source):
    """Test finding document by non-existent external ID returns None."""
    repo = DocumentRepository(session, tenant.id)

    found = await repo.find_by_external_id(data_source.id, "nonexistent")

    assert found is None


@pytest.mark.asyncio
async def test_find_pending(session: AsyncSession, tenant, data_source):
    """Test finding pending documents."""
    repo = DocumentRepository(session, tenant.id)

    # Create documents with different statuses
    pending1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="pending-1",
        title="Pending 1",
        content="Content",
        content_type="text/plain",
        content_hash="p1hash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    pending2 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="pending-2",
        title="Pending 2",
        content="Content",
        content_type="text/plain",
        content_hash="p2hash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    completed = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="completed-1",
        title="Completed 1",
        content="Content",
        content_type="text/plain",
        content_hash="c1hash",
        metadata={},
        file_size=100,
        processed_status="completed",
    )

    session.add_all([pending1, pending2, completed])
    await session.flush()

    pending_docs = await repo.find_pending(limit=10)

    pending_ids = {d.id for d in pending_docs}
    assert pending1.id in pending_ids
    assert pending2.id in pending_ids
    assert completed.id not in pending_ids


@pytest.mark.asyncio
async def test_find_pending_with_limit(session: AsyncSession, tenant, data_source):
    """Test finding pending documents with limit."""
    repo = DocumentRepository(session, tenant.id)

    # Create 5 pending documents
    for i in range(5):
        doc = Document(
            id=uuid4(),
            tenant_id=tenant.id,
            data_source_id=data_source.id,
            external_id=f"pending-{i}",
            title=f"Pending {i}",
            content="Content",
            content_type="text/plain",
            content_hash=f"hash-{i}",
            metadata={},
            file_size=100,
            processed_status="pending",
        )
        session.add(doc)
    await session.flush()

    pending_docs = await repo.find_pending(limit=3)

    assert len(pending_docs) == 3


@pytest.mark.asyncio
async def test_update_status(session: AsyncSession, tenant, data_source):
    """Test updating document status."""
    repo = DocumentRepository(session, tenant.id)

    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-status",
        title="Status Doc",
        content="Content",
        content_type="text/plain",
        content_hash="statushash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo.create(doc)

    await repo.update_status(doc.id, "processing")

    updated = await repo.get_by_id(doc.id)
    assert updated.processed_status == "processing"


@pytest.mark.asyncio
async def test_update_status_completed(session: AsyncSession, tenant, data_source):
    """Test updating document status to completed sets processed_at."""
    repo = DocumentRepository(session, tenant.id)

    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-complete",
        title="Complete Doc",
        content="Content",
        content_type="text/plain",
        content_hash="completehash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo.create(doc)

    await repo.update_status(doc.id, "completed")

    updated = await repo.get_by_id(doc.id)
    assert updated.processed_status == "completed"
    assert updated.processed_at is not None


@pytest.mark.asyncio
async def test_update_status_failed(session: AsyncSession, tenant, data_source):
    """Test updating document status to failed with error message."""
    repo = DocumentRepository(session, tenant.id)

    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-failed",
        title="Failed Doc",
        content="Content",
        content_type="text/plain",
        content_hash="failedhash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo.create(doc)

    await repo.update_status(doc.id, "failed", "Processing error occurred")

    updated = await repo.get_by_id(doc.id)
    assert updated.processed_status == "failed"
    assert updated.error_message == "Processing error occurred"


@pytest.mark.asyncio
async def test_search_fulltext(session: AsyncSession, tenant, data_source):
    """Test full-text search across documents."""
    repo = DocumentRepository(session, tenant.id)

    # Create documents with searchable content
    doc1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="search-1",
        title="Python Programming Guide",
        content="Learn Python programming with examples and best practices",
        content_type="text/plain",
        content_hash="search1",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    doc2 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="search-2",
        title="Java Development",
        content="Java programming language tutorial and reference",
        content_type="text/plain",
        content_hash="search2",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    doc3 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="search-3",
        title="Python Data Science",
        content="Using Python for data science and machine learning",
        content_type="text/plain",
        content_hash="search3",
        metadata={},
        file_size=100,
        processed_status="completed",
    )

    session.add_all([doc1, doc2, doc3])
    await session.flush()

    # Search for "Python"
    page = PageRequest(page=0, size=10)
    results = await repo.search_fulltext("Python", page)

    # Should find doc1 and doc3, not doc2
    found_ids = {d.id for d in results.content}
    assert doc1.id in found_ids
    assert doc3.id in found_ids
    assert doc2.id not in found_ids


@pytest.mark.asyncio
async def test_search_fulltext_pagination(session: AsyncSession, tenant, data_source):
    """Test full-text search with pagination."""
    repo = DocumentRepository(session, tenant.id)

    # Create multiple documents with "test" keyword
    for i in range(5):
        doc = Document(
            id=uuid4(),
            tenant_id=tenant.id,
            data_source_id=data_source.id,
            external_id=f"test-{i}",
            title=f"Test Document {i}",
            content=f"This is test content number {i}",
            content_type="text/plain",
            content_hash=f"testhash{i}",
            metadata={},
            file_size=100,
            processed_status="completed",
        )
        session.add(doc)
    await session.flush()

    # Get first page
    page = PageRequest(page=0, size=2)
    results = await repo.search_fulltext("test", page)

    assert len(results.content) == 2
    assert results.total_elements >= 5
    assert results.current_page == 0


@pytest.mark.asyncio
async def test_search_fulltext_no_results(session: AsyncSession, tenant):
    """Test full-text search with no matching results."""
    repo = DocumentRepository(session, tenant.id)

    page = PageRequest(page=0, size=10)
    results = await repo.search_fulltext("nonexistentkeyword", page)

    assert len(results.content) == 0
    assert results.total_elements == 0


@pytest.mark.asyncio
async def test_tenant_isolation_find_by_hash(
    session: AsyncSession, tenant, second_tenant, data_source
):
    """Test that find_by_hash respects tenant isolation."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create document in tenant1
    doc = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="isolated-1",
        title="Isolated Doc",
        content="Content",
        content_type="text/plain",
        content_hash="isolatedhash",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo1.create(doc)

    # Try to find from tenant2
    found = await repo2.find_by_hash("isolatedhash")

    assert found is None
