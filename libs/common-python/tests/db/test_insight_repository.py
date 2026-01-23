"""Tests for insight repository specialized queries."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models import Insight
from aswa_common.db.repositories.insight_repository import InsightRepository
from aswa_common.models import PageRequest


@pytest.mark.asyncio
async def test_find_by_type(session: AsyncSession, tenant):
    """Test finding insights by type."""
    repo = InsightRepository(session, tenant.id)

    # Create insights of different types
    entity = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Entity Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    risk = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Risk Insight",
        content={},
        confidence=0.85,
        source_documents=[],
    )
    opportunity = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="opportunity",
        title="Opportunity Insight",
        content={},
        confidence=0.8,
        source_documents=[],
    )

    session.add_all([entity, risk, opportunity])
    await session.flush()

    # Find entity type
    page = PageRequest(page=0, size=10)
    results = await repo.find_by_type("entity", page)

    found_ids = {i.id for i in results.content}
    assert entity.id in found_ids
    assert risk.id not in found_ids
    assert opportunity.id not in found_ids


@pytest.mark.asyncio
async def test_find_by_type_pagination(session: AsyncSession, tenant):
    """Test finding insights by type with pagination."""
    repo = InsightRepository(session, tenant.id)

    # Create multiple risk insights
    for i in range(5):
        insight = Insight(
            id=uuid4(),
            tenant_id=tenant.id,
            insight_type="risk",
            title=f"Risk {i}",
            content={},
            confidence=0.8,
            source_documents=[],
        )
        session.add(insight)
    await session.flush()

    # Get first page
    page = PageRequest(page=0, size=2)
    results = await repo.find_by_type("risk", page)

    assert len(results.content) == 2
    assert results.total_elements >= 5


@pytest.mark.asyncio
async def test_find_by_documents(session: AsyncSession, tenant):
    """Test finding insights that reference specific documents."""
    repo = InsightRepository(session, tenant.id)

    doc1_id = uuid4()
    doc2_id = uuid4()
    doc3_id = uuid4()

    # Create insights referencing different documents
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Insight 1",
        content={},
        confidence=0.9,
        source_documents=[doc1_id, doc2_id],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Insight 2",
        content={},
        confidence=0.85,
        source_documents=[doc2_id, doc3_id],
    )
    insight3 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="opportunity",
        title="Insight 3",
        content={},
        confidence=0.8,
        source_documents=[doc3_id],
    )

    session.add_all([insight1, insight2, insight3])
    await session.flush()

    # Find insights referencing doc2
    results = await repo.find_by_documents([doc2_id])

    found_ids = {i.id for i in results}
    assert insight1.id in found_ids
    assert insight2.id in found_ids
    assert insight3.id not in found_ids


@pytest.mark.asyncio
async def test_find_by_documents_multiple(session: AsyncSession, tenant):
    """Test finding insights referencing any of multiple documents."""
    repo = InsightRepository(session, tenant.id)

    doc1_id = uuid4()
    doc2_id = uuid4()
    doc3_id = uuid4()

    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Insight 1",
        content={},
        confidence=0.9,
        source_documents=[doc1_id],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Insight 2",
        content={},
        confidence=0.85,
        source_documents=[doc2_id],
    )
    insight3 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="opportunity",
        title="Insight 3",
        content={},
        confidence=0.8,
        source_documents=[doc3_id],
    )

    session.add_all([insight1, insight2, insight3])
    await session.flush()

    # Find insights referencing doc1 OR doc2
    results = await repo.find_by_documents([doc1_id, doc2_id])

    found_ids = {i.id for i in results}
    assert insight1.id in found_ids
    assert insight2.id in found_ids
    assert insight3.id not in found_ids


@pytest.mark.asyncio
async def test_search_fulltext(session: AsyncSession, tenant):
    """Test full-text search across insights."""
    repo = InsightRepository(session, tenant.id)

    # Create insights with searchable content
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Security Vulnerability Detected",
        description="Critical security vulnerability found in authentication system",
        content={},
        confidence=0.95,
        source_documents=[],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Performance Issue",
        description="Database query performance degradation observed",
        content={},
        confidence=0.85,
        source_documents=[],
    )
    insight3 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="opportunity",
        title="Security Enhancement Opportunity",
        description="Opportunity to improve security posture with MFA",
        content={},
        confidence=0.8,
        source_documents=[],
    )

    session.add_all([insight1, insight2, insight3])
    await session.flush()

    # Search for "security"
    page = PageRequest(page=0, size=10)
    results = await repo.search_fulltext("security", page)

    # Should find insight1 and insight3, not insight2
    found_ids = {i.id for i in results.content}
    assert insight1.id in found_ids
    assert insight3.id in found_ids
    assert insight2.id not in found_ids


@pytest.mark.asyncio
async def test_search_fulltext_ranking(session: AsyncSession, tenant):
    """Test full-text search returns results ranked by relevance."""
    repo = InsightRepository(session, tenant.id)

    # Create insights with varying relevance
    highly_relevant = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Python Python Python",
        description="Python programming language Python development",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    less_relevant = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Software Development",
        description="General software development including Python",
        content={},
        confidence=0.85,
        source_documents=[],
    )

    session.add_all([highly_relevant, less_relevant])
    await session.flush()

    # Search for "Python"
    page = PageRequest(page=0, size=10)
    results = await repo.search_fulltext("Python", page)

    # Highly relevant should be first (ranked higher)
    assert len(results.content) == 2
    assert results.content[0].id == highly_relevant.id


@pytest.mark.asyncio
async def test_update_feedback(session: AsyncSession, tenant, user):
    """Test updating user feedback on an insight."""
    repo = InsightRepository(session, tenant.id)

    insight = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Risk Insight",
        content={},
        confidence=0.8,
        source_documents=[],
    )
    await repo.create(insight)

    await repo.update_feedback(insight.id, "confirmed", user.id, "This is accurate")

    updated = await repo.get_by_id(insight.id)
    assert updated.user_feedback == "confirmed"
    assert updated.feedback_by == user.id
    assert updated.feedback_comment == "This is accurate"
    assert updated.feedback_at is not None


@pytest.mark.asyncio
async def test_update_feedback_rejected(session: AsyncSession, tenant, user):
    """Test updating feedback to rejected."""
    repo = InsightRepository(session, tenant.id)

    insight = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Entity Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    await repo.create(insight)

    await repo.update_feedback(insight.id, "rejected", user.id, "Not accurate")

    updated = await repo.get_by_id(insight.id)
    assert updated.user_feedback == "rejected"
    assert updated.feedback_comment == "Not accurate"


@pytest.mark.asyncio
async def test_aggregate_by_type(session: AsyncSession, tenant):
    """Test aggregating insights count by type."""
    repo = InsightRepository(session, tenant.id)

    # Create insights of different types
    for i in range(3):
        session.add(
            Insight(
                id=uuid4(),
                tenant_id=tenant.id,
                insight_type="entity",
                title=f"Entity {i}",
                content={},
                confidence=0.9,
                source_documents=[],
            )
        )
    for i in range(2):
        session.add(
            Insight(
                id=uuid4(),
                tenant_id=tenant.id,
                insight_type="risk",
                title=f"Risk {i}",
                content={},
                confidence=0.85,
                source_documents=[],
            )
        )
    session.add(
        Insight(
            id=uuid4(),
            tenant_id=tenant.id,
            insight_type="opportunity",
            title="Opportunity",
            content={},
            confidence=0.8,
            source_documents=[],
        )
    )
    await session.flush()

    aggregation = await repo.aggregate_by_type()

    assert aggregation["entity"] == 3
    assert aggregation["risk"] == 2
    assert aggregation["opportunity"] == 1


@pytest.mark.asyncio
async def test_find_recent(session: AsyncSession, tenant):
    """Test finding recent insights within specified days."""
    repo = InsightRepository(session, tenant.id)

    # Create insights with different timestamps
    recent = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Recent Insight",
        content={},
        confidence=0.9,
        source_documents=[],
        status="active",
    )
    session.add(recent)
    await session.flush()

    # Create old insight by manually setting created_at
    old = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Old Insight",
        content={},
        confidence=0.85,
        source_documents=[],
        status="active",
    )
    session.add(old)
    await session.flush()

    # Manually update created_at to 10 days ago
    old.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    await session.flush()

    # Find insights from last 7 days
    results = await repo.find_recent(days=7, limit=100)

    found_ids = {i.id for i in results}
    assert recent.id in found_ids
    assert old.id not in found_ids


@pytest.mark.asyncio
async def test_find_recent_with_limit(session: AsyncSession, tenant):
    """Test finding recent insights with limit."""
    repo = InsightRepository(session, tenant.id)

    # Create 5 recent insights
    for i in range(5):
        insight = Insight(
            id=uuid4(),
            tenant_id=tenant.id,
            insight_type="entity",
            title=f"Recent {i}",
            content={},
            confidence=0.9,
            source_documents=[],
            status="active",
        )
        session.add(insight)
    await session.flush()

    results = await repo.find_recent(days=7, limit=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_find_recent_excludes_inactive(session: AsyncSession, tenant):
    """Test that find_recent only returns active insights."""
    repo = InsightRepository(session, tenant.id)

    active = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Active Insight",
        content={},
        confidence=0.9,
        source_documents=[],
        status="active",
    )
    inactive = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Inactive Insight",
        content={},
        confidence=0.85,
        source_documents=[],
        status="archived",
    )

    session.add_all([active, inactive])
    await session.flush()

    results = await repo.find_recent(days=7, limit=100)

    found_ids = {i.id for i in results}
    assert active.id in found_ids
    assert inactive.id not in found_ids


@pytest.mark.asyncio
async def test_tenant_isolation_find_by_type(session: AsyncSession, tenant, second_tenant):
    """Test that find_by_type respects tenant isolation."""
    repo1 = InsightRepository(session, tenant.id)
    repo2 = InsightRepository(session, second_tenant.id)

    # Create insights in tenant1
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Tenant 1 Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    # Create insights in tenant2
    insight2 = Insight(
        id=uuid4(),
        tenant_id=second_tenant.id,
        insight_type="entity",
        title="Tenant 2 Insight",
        content={},
        confidence=0.9,
        source_documents=[],
    )

    session.add_all([insight1, insight2])
    await session.flush()

    # Find from tenant1
    page = PageRequest(page=0, size=10)
    results1 = await repo1.find_by_type("entity", page)

    found_ids1 = {i.id for i in results1.content}
    assert insight1.id in found_ids1
    assert insight2.id not in found_ids1

    # Find from tenant2
    results2 = await repo2.find_by_type("entity", page)

    found_ids2 = {i.id for i in results2.content}
    assert insight2.id in found_ids2
    assert insight1.id not in found_ids2
