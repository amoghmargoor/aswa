"""Tests for SQLAlchemy models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models import (
    DataSource,
    Document,
    DocumentChunk,
    EntityRelationship,
    Insight,
    Tenant,
    User,
)


@pytest.mark.asyncio
async def test_tenant_creation(session: AsyncSession):
    """Test tenant model creation."""
    tenant = Tenant(
        id=uuid4(),
        name="ACME Corp",
        slug="acme-corp",
        settings={"max_users": 100},
        status="active",
    )
    session.add(tenant)
    await session.flush()
    await session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.name == "ACME Corp"
    assert tenant.slug == "acme-corp"
    assert tenant.settings["max_users"] == 100
    assert tenant.status == "active"
    assert tenant.created_at is not None
    assert tenant.updated_at is not None


@pytest.mark.asyncio
async def test_user_creation(session: AsyncSession, tenant: Tenant):
    """Test user model creation and tenant relationship."""
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="jane@example.com",
        full_name="Jane Doe",
        password_hash="hashed_password_123",
        role="user",
        status="active",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    assert user.id is not None
    assert user.tenant_id == tenant.id
    assert user.email == "jane@example.com"
    assert user.full_name == "Jane Doe"
    assert user.role == "user"
    assert user.status == "active"
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_tenant_cascade_delete(session: AsyncSession):
    """Test that deleting tenant cascades to users."""
    tenant = Tenant(
        id=uuid4(),
        name="Temp Corp",
        slug="temp-corp",
        settings={},
        status="active",
    )
    session.add(tenant)
    await session.flush()

    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="temp@example.com",
        full_name="Temp User",
        password_hash="hash",
        role="user",
        status="active",
    )
    session.add(user)
    await session.flush()

    user_id = user.id

    # Delete tenant
    await session.delete(tenant)
    await session.flush()

    # Verify user was cascaded
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None


@pytest.mark.asyncio
async def test_data_source_creation(session: AsyncSession, tenant: Tenant):
    """Test data source model creation."""
    data_source = DataSource(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Confluence",
        source_type="confluence",
        config={"base_url": "https://confluence.example.com"},
        credentials={"api_key": "secret"},
        status="active",
        last_sync_at=None,
    )
    session.add(data_source)
    await session.flush()
    await session.refresh(data_source)

    assert data_source.id is not None
    assert data_source.tenant_id == tenant.id
    assert data_source.name == "Confluence"
    assert data_source.source_type == "confluence"
    assert data_source.config["base_url"] == "https://confluence.example.com"
    assert data_source.status == "active"


@pytest.mark.asyncio
async def test_document_creation(session: AsyncSession, tenant: Tenant):
    """Test document model creation."""
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

    document = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-123",
        title="Test Document",
        content="This is test content",
        content_type="text/plain",
        content_hash="abc123",
        metadata={"author": "Test Author"},
        file_size=100,
        processed_status="pending",
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)

    assert document.id is not None
    assert document.tenant_id == tenant.id
    assert document.data_source_id == data_source.id
    assert document.title == "Test Document"
    assert document.content == "This is test content"
    assert document.processed_status == "pending"


@pytest.mark.asyncio
async def test_document_chunk_creation(session: AsyncSession, tenant: Tenant):
    """Test document chunk model creation."""
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

    document = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-456",
        title="Chunked Document",
        content="Full content",
        content_type="text/plain",
        content_hash="def456",
        metadata={},
        file_size=100,
        processed_status="completed",
    )
    session.add(document)
    await session.flush()

    chunk = DocumentChunk(
        id=uuid4(),
        tenant_id=tenant.id,
        document_id=document.id,
        chunk_index=0,
        content="First chunk of content",
        chunk_metadata={"tokens": 5},
        vector_id="vec-001",
    )
    session.add(chunk)
    await session.flush()
    await session.refresh(chunk)

    assert chunk.id is not None
    assert chunk.tenant_id == tenant.id
    assert chunk.document_id == document.id
    assert chunk.chunk_index == 0
    assert chunk.content == "First chunk of content"
    assert chunk.vector_id == "vec-001"


@pytest.mark.asyncio
async def test_insight_creation(session: AsyncSession, tenant: Tenant):
    """Test insight model creation."""
    doc_id = uuid4()
    insight = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Important Entity",
        description="This is an important entity found in documents",
        content={"entity_name": "ACME Corp", "entity_type": "organization"},
        confidence=0.95,
        severity="high",
        category="business",
        tags=["entity", "organization"],
        source_documents=[doc_id],
        evidence_snippets=["ACME Corp is mentioned here"],
        status="active",
    )
    session.add(insight)
    await session.flush()
    await session.refresh(insight)

    assert insight.id is not None
    assert insight.tenant_id == tenant.id
    assert insight.insight_type == "entity"
    assert insight.title == "Important Entity"
    assert insight.confidence == 0.95
    assert insight.severity == "high"
    assert len(insight.tags) == 2
    assert len(insight.source_documents) == 1
    assert insight.status == "active"


@pytest.mark.asyncio
async def test_entity_relationship_creation(session: AsyncSession, tenant: Tenant):
    """Test entity relationship model creation."""
    insight1 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Entity 1",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    insight2 = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="entity",
        title="Entity 2",
        content={},
        confidence=0.9,
        source_documents=[],
    )
    session.add_all([insight1, insight2])
    await session.flush()

    relationship = EntityRelationship(
        id=uuid4(),
        tenant_id=tenant.id,
        source_insight_id=insight1.id,
        target_insight_id=insight2.id,
        relationship_type="related_to",
        direction="directed",
        confidence=0.85,
        evidence="They appear in the same document",
        metadata={"strength": "strong"},
    )
    session.add(relationship)
    await session.flush()
    await session.refresh(relationship)

    assert relationship.id is not None
    assert relationship.tenant_id == tenant.id
    assert relationship.source_insight_id == insight1.id
    assert relationship.target_insight_id == insight2.id
    assert relationship.relationship_type == "related_to"
    assert relationship.confidence == 0.85
    assert relationship.created_at is not None


@pytest.mark.asyncio
async def test_insight_feedback_update(session: AsyncSession, tenant: Tenant, user: User):
    """Test updating feedback on an insight."""
    insight = Insight(
        id=uuid4(),
        tenant_id=tenant.id,
        insight_type="risk",
        title="Risk Insight",
        content={},
        confidence=0.8,
        source_documents=[],
    )
    session.add(insight)
    await session.flush()

    # Update feedback
    insight.user_feedback = "confirmed"
    insight.feedback_by = user.id
    insight.feedback_comment = "This is accurate"
    insight.feedback_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(insight)

    assert insight.user_feedback == "confirmed"
    assert insight.feedback_by == user.id
    assert insight.feedback_comment == "This is accurate"
    assert insight.feedback_at is not None


@pytest.mark.asyncio
async def test_document_status_update(session: AsyncSession, tenant: Tenant):
    """Test updating document processing status."""
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

    document = Document(
        id=uuid4(),
        tenant_id=tenant.id,
        data_source_id=data_source.id,
        external_id="doc-789",
        title="Processing Document",
        content="Content",
        content_type="text/plain",
        content_hash="ghi789",
        metadata={},
        file_size=50,
        processed_status="pending",
    )
    session.add(document)
    await session.flush()

    # Update status
    document.processed_status = "completed"
    document.processed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(document)

    assert document.processed_status == "completed"
    assert document.processed_at is not None
