"""Tests for tenant isolation enforcement across all repositories."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models import DataSource, Document, Insight
from aswa_common.db.repositories.document_repository import DocumentRepository
from aswa_common.db.repositories.insight_repository import InsightRepository
from aswa_common.models import PageRequest


@pytest.mark.asyncio
async def test_document_repository_cannot_access_other_tenant_documents(
    session: AsyncSession, tenant, second_tenant
):
    """Test that document repository cannot access documents from other tenants."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create data sources for each tenant
    ds1 = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Source 1",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    ds2 = DataSource(
        id=uuid4(),
        tenant_id=second_tenant.id,
        name="Source 2",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add_all([ds1, ds2])
    await session.flush()

    # Create document in tenant1
    doc1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=ds1.id,
        external_id="doc-1",
        title="Tenant 1 Doc",
        content="Content 1",
        content_type="text/plain",
        content_hash="hash1",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    await repo1.create(doc1)

    # Try to access from tenant2
    found = await repo2.get_by_id(doc1.id)
    assert found is None

    # Try to find in get_all
    page = PageRequest(page=0, size=10)
    all_docs = await repo2.get_all(page)
    doc_ids = {d.id for d in all_docs.content}
    assert doc1.id not in doc_ids


@pytest.mark.asyncio
async def test_insight_repository_cannot_access_other_tenant_insights(
    session: AsyncSession, tenant, second_tenant
):
    """Test that insight repository cannot access insights from other tenants."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    # Create insight in tenant1
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Tenant 1 Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    await repo1.create(insight1)

    # Try to access from tenant2
    found = await repo2.get_by_id(insight1.id)
    assert found is None

    # Try to find in get_all
    page = PageRequest(page=0, size=10)
    all_insights = await repo2.get_all(page)
    insight_ids = {i.id for i in all_insights.content}
    assert insight1.id not in insight_ids


@pytest.mark.asyncio
async def test_document_delete_only_affects_own_tenant(
    session: AsyncSession, tenant, second_tenant
):
    """Test that deleting document only affects own tenant."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create data sources
    ds1 = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Source 1",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    ds2 = DataSource(
        id=uuid4(),
        tenant_id=second_tenant.id,
        name="Source 2",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add_all([ds1, ds2])
    await session.flush()

    # Create documents in both tenants with same ID (hypothetically)
    doc_id = uuid4()
    doc1 = Document(
        id=doc_id,
        tenant_id=tenant.id,
        data_source_id=ds1.id,
        external_id="doc-shared",
        title="Tenant 1 Doc",
        content="Content 1",
        content_type="text/plain",
        content_hash="hash1",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    await repo1.create(doc1)

    # Try to delete from tenant2 (should fail)
    deleted = await repo2.delete(doc_id)
    assert deleted is False

    # Verify doc1 still exists in tenant1
    found = await repo1.get_by_id(doc_id)
    assert found is not None


@pytest.mark.asyncio
async def test_insight_delete_only_affects_own_tenant(
    session: AsyncSession, tenant, second_tenant
):
    """Test that deleting insight only affects own tenant."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    # Create insight in tenant1
    insight_id = uuid4()
    insight1 = Insight(
        id=insight_id,
        tenant_id=tenant.id,
        insight_type="entity",
        title="Tenant 1 Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    await repo1.create(insight1)

    # Try to delete from tenant2 (should fail)
    deleted = await repo2.delete(insight_id)
    assert deleted is False

    # Verify insight1 still exists in tenant1
    found = await repo1.get_by_id(insight_id)
    assert found is not None


@pytest.mark.asyncio
async def test_document_update_only_affects_own_tenant(
    session: AsyncSession, tenant, second_tenant
):
    """Test that updating document only works within own tenant."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create data source
    ds1 = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Source 1",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add(ds1)
    await session.flush()

    # Create document in tenant1
    doc1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=ds1.id,
        external_id="doc-update",
        title="Original Title",
        content="Original Content",
        content_type="text/plain",
        content_hash="hash-update",
        metadata={},
        file_size=100,
        processed_status="pending",
    )
    await repo1.create(doc1)

    # Try to update status from tenant2 (should not work)
    await repo2.update_status(doc1.id, "completed")

    # Verify status unchanged in tenant1
    found = await repo1.get_by_id(doc1.id)
    assert found.processed_status == "pending"  # Should still be pending


@pytest.mark.asyncio
async def test_fulltext_search_respects_tenant_isolation(
    session: AsyncSession, tenant, second_tenant
):
    """Test that full-text search only finds results within tenant."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create data sources
    ds1 = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Source 1",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    ds2 = DataSource(
        id=uuid4(),
        tenant_id=second_tenant.id,
        name="Source 2",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add_all([ds1, ds2])
    await session.flush()

    # Create documents with same keyword in different tenants
    doc1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=ds1.id,
        external_id="search-1",
        title="Python Programming for Tenant 1",
        content="Learn Python in tenant 1",
        content_type="text/plain",
        content_hash="search1",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    doc2 = Document(
        id=uuid4(),
        tenant_id=second_tenant.id,
        data_source_id=ds2.id,
        external_id="search-2",
        title="Python Programming for Tenant 2",
        content="Learn Python in tenant 2",
        content_type="text/plain",
        content_hash="search2",
        metadata={},
        file_size=100,
        processed_status="completed",
    )

    session.add_all([doc1, doc2])
    await session.flush()

    # Search from tenant1
    page = PageRequest(page=0, size=10)
    results1 = await repo1.search_fulltext("Python", page)

    found_ids1 = {d.id for d in results1.content}
    assert doc1.id in found_ids1
    assert doc2.id not in found_ids1

    # Search from tenant2
    results2 = await repo2.search_fulltext("Python", page)

    found_ids2 = {d.id for d in results2.content}
    assert doc2.id in found_ids2
    assert doc1.id not in found_ids2


@pytest.mark.asyncio
async def test_insight_fulltext_search_respects_tenant_isolation(
    session: AsyncSession, tenant, second_tenant
):
    """Test that insight full-text search only finds results within tenant."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    # Create insights with same keyword in different tenants
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Security Issue in Tenant 1",
        description="Security vulnerability detected",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=second_tenant.id,
        insight_type="entity",
        title="Security Issue in Tenant 2",
        description="Security vulnerability detected",
        content={},
        confidence=0.9,
        source_documents=[],
    )

    session.add_all([insight1, insight2])
    await session.flush()

    # Search from tenant1
    page = PageRequest(page=0, size=10)
    results1 = await repo1.search_fulltext("security", page)

    found_ids1 = {i.id for i in results1.content}
    assert insight1.id in found_ids1
    assert insight2.id not in found_ids1

    # Search from tenant2
    results2 = await repo2.search_fulltext("security", page)

    found_ids2 = {i.id for i in results2.content}
    assert insight2.id in found_ids2
    assert insight1.id not in found_ids2


@pytest.mark.asyncio
async def test_aggregate_respects_tenant_isolation(
    session: AsyncSession, tenant, second_tenant
):
    """Test that aggregate functions respect tenant isolation."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    # Create insights in tenant1
    for i in range(3):
        insight = Insight(
            id=uuid4(),
            tenant_id=tenant.id,
            insight_type="entity",
            title=f"Tenant 1 Entity {i}",
            content={},
            confidence=0.9,
            source_documents=[],
        )
        session.add(insight)

    # Create insights in tenant2
    for i in range(2):
        insight = Insight(
            id=uuid4(),
            tenant_id=second_tenant.id,
            insight_type="entity",
            title=f"Tenant 2 Entity {i}",
            content={},
            confidence=0.9,
            source_documents=[],
        )
        session.add(insight)

    await session.flush()

    # Aggregate for tenant1
    agg1 = await repo1.aggregate_by_type()
    assert agg1.get("entity", 0) == 3

    # Aggregate for tenant2
    agg2 = await repo2.aggregate_by_type()
    assert agg2.get("entity", 0) == 2


@pytest.mark.asyncio
async def test_exists_respects_tenant_isolation(
    session: AsyncSession, tenant, second_tenant
):
    """Test that exists check respects tenant isolation."""
    repo1 = DocumentRepository(session, tenant.id)
    repo2 = DocumentRepository(session, second_tenant.id)

    # Create data source
    ds1 = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Source 1",
        source_type="test",
        config={},
        credentials={},
        status="active",
    )
    session.add(ds1)
    await session.flush()

    # Create document in tenant1
    doc1 = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=ds1.id,
        external_id="doc-exists",
        title="Exists Test",
        content="Content",
        content_type="text/plain",
        content_hash="existshash",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    await repo1.create(doc1)

    # Check exists in tenant1
    exists1 = await repo1.exists(doc1.id)
    assert exists1 is True

    # Check exists in tenant2 (should be False)
    exists2 = await repo2.exists(doc1.id)
    assert exists2 is False


@pytest.mark.asyncio
async def test_find_by_documents_respects_tenant_isolation(
    session: AsyncSession, tenant, second_tenant
):
    """Test that find_by_documents respects tenant isolation."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    doc_id = uuid4()

    # Create insights in different tenants referencing same document
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Tenant 1 Insight",
        content={},
        confidence=0.9,
        source_documents=[doc_id],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=second_tenant.id,
        insight_type="entity",
        title="Tenant 2 Insight",
        content={},
        confidence=0.9,
        source_documents=[doc_id],
    )

    session.add_all([insight1, insight2])
    await session.flush()

    # Find from tenant1
    results1 = await repo1.find_by_documents([doc_id])
    found_ids1 = {i.id for i in results1}
    assert insight1.id in found_ids1
    assert insight2.id not in found_ids1

    # Find from tenant2
    results2 = await repo2.find_by_documents([doc_id])
    found_ids2 = {i.id for i in results2}
    assert insight2.id in found_ids2
    assert insight1.id not in found_ids2
