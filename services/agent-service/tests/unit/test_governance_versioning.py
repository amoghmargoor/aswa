"""Tests for governance versioning and audit logging."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from aswa_agents.governance import (
    AgentVersion,
    AuditAction,
    AuditEntry,
    AuditLogger,
    VersionDiff,
    VersionManager,
    VersionStatus,
)


class TestVersionManager:
    """Tests for VersionManager class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def manager(self, tenant_id):
        """Create a version manager instance."""
        return VersionManager(tenant_id)

    @pytest.fixture
    def agent_id(self):
        """Create an agent ID for testing."""
        return uuid4()

    @pytest.fixture
    def sample_definition(self):
        """Create a sample agent definition."""
        return {
            "trigger": {"type": "schedule", "config": {"frequency": "daily"}},
            "actions": [
                {"id": "action1", "type": "summarize", "config": {"style": "brief"}}
            ],
        }

    @pytest.mark.asyncio
    async def test_create_version(self, manager, agent_id, sample_definition):
        """Test creating a new version."""
        user_id = uuid4()

        version = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
            changelog="Initial version",
        )

        assert version.agent_id == agent_id
        assert version.version_number == 1
        assert version.status == VersionStatus.DRAFT
        assert version.definition == sample_definition
        assert version.created_by == user_id
        assert version.changelog == "Initial version"

    @pytest.mark.asyncio
    async def test_create_subsequent_version(self, manager, agent_id, sample_definition):
        """Test creating subsequent versions."""
        user_id = uuid4()

        v1 = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )

        updated_definition = {
            **sample_definition,
            "actions": [
                {"id": "action1", "type": "summarize", "config": {"style": "detailed"}}
            ],
        }

        v2 = await manager.create_version(
            agent_id=agent_id,
            definition=updated_definition,
            created_by=user_id,
            changelog="Changed summary style",
        )

        assert v2.version_number == 2
        assert v2.changelog == "Changed summary style"

    @pytest.mark.asyncio
    async def test_get_versions(self, manager, agent_id, sample_definition):
        """Test getting all versions for an agent."""
        user_id = uuid4()

        for i in range(3):
            await manager.create_version(
                agent_id=agent_id,
                definition=sample_definition,
                created_by=user_id,
                changelog=f"Version {i + 1}",
            )

        versions = await manager.get_versions(agent_id)

        assert len(versions) == 3
        assert versions[0].version_number == 1
        assert versions[2].version_number == 3

    @pytest.mark.asyncio
    async def test_get_specific_version(self, manager, agent_id, sample_definition):
        """Test getting a specific version."""
        user_id = uuid4()

        await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )

        version = await manager.get_version(agent_id, 1)

        assert version is not None
        assert version.version_number == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_version(self, manager, agent_id):
        """Test getting a version that doesn't exist."""
        version = await manager.get_version(agent_id, 999)

        assert version is None

    @pytest.mark.asyncio
    async def test_publish_version(self, manager, agent_id, sample_definition):
        """Test publishing a version."""
        user_id = uuid4()

        version = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )

        published = await manager.publish_version(agent_id, version.id, user_id)

        assert published.status == VersionStatus.PUBLISHED
        assert published.published_at is not None
        assert published.published_by == user_id

    @pytest.mark.asyncio
    async def test_archive_version(self, manager, agent_id, sample_definition):
        """Test archiving a version."""
        user_id = uuid4()

        version = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )

        await manager.publish_version(agent_id, version.id, user_id)
        archived = await manager.archive_version(agent_id, version.id)

        assert archived.status == VersionStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_rollback(self, manager, agent_id, sample_definition):
        """Test rolling back to a previous version."""
        user_id = uuid4()

        # Create and publish v1
        v1 = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )
        await manager.publish_version(agent_id, v1.id, user_id)

        # Create and publish v2
        v2_def = {**sample_definition, "actions": []}
        v2 = await manager.create_version(
            agent_id=agent_id,
            definition=v2_def,
            created_by=user_id,
        )
        await manager.publish_version(agent_id, v2.id, user_id)

        # Rollback to v1
        rolled_back = await manager.rollback(agent_id, 1, user_id)

        assert rolled_back.version_number == 3  # New version created
        assert rolled_back.definition == sample_definition
        assert "Rollback" in rolled_back.changelog

    @pytest.mark.asyncio
    async def test_compare_versions(self, manager, agent_id, sample_definition):
        """Test comparing two versions."""
        user_id = uuid4()

        v1 = await manager.create_version(
            agent_id=agent_id,
            definition=sample_definition,
            created_by=user_id,
        )

        v2_def = {
            **sample_definition,
            "actions": [
                {"id": "action1", "type": "summarize", "config": {"style": "detailed"}}
            ],
        }
        v2 = await manager.create_version(
            agent_id=agent_id,
            definition=v2_def,
            created_by=user_id,
        )

        diff = await manager.compare_versions(agent_id, 1, 2)

        assert isinstance(diff, VersionDiff)
        assert diff.from_version == 1
        assert diff.to_version == 2
        assert len(diff.changes) > 0


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def logger(self, tenant_id):
        """Create an audit logger instance."""
        return AuditLogger(tenant_id)

    @pytest.mark.asyncio
    async def test_log_action(self, logger):
        """Test logging an action."""
        actor_id = uuid4()
        resource_id = uuid4()

        entry = await logger.log(
            action=AuditAction.AGENT_CREATED,
            actor_id=actor_id,
            resource_id=resource_id,
            details={"name": "test-agent"},
        )

        assert entry.action == AuditAction.AGENT_CREATED
        assert entry.actor_id == actor_id
        assert entry.resource_id == resource_id
        assert entry.details["name"] == "test-agent"
        assert entry.timestamp is not None

    @pytest.mark.asyncio
    async def test_query_by_resource(self, logger):
        """Test querying audit log by resource."""
        resource_id = uuid4()

        # Log multiple actions for the same resource
        for action in [AuditAction.AGENT_CREATED, AuditAction.AGENT_UPDATED]:
            await logger.log(
                action=action,
                actor_id=uuid4(),
                resource_id=resource_id,
                details={},
            )

        entries = await logger.query(resource_id=resource_id)

        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_query_by_actor(self, logger):
        """Test querying audit log by actor."""
        actor_id = uuid4()

        for _ in range(3):
            await logger.log(
                action=AuditAction.AGENT_CREATED,
                actor_id=actor_id,
                resource_id=uuid4(),
                details={},
            )

        entries = await logger.query(actor_id=actor_id)

        assert len(entries) == 3
        assert all(e.actor_id == actor_id for e in entries)

    @pytest.mark.asyncio
    async def test_query_by_action(self, logger):
        """Test querying audit log by action type."""
        resource_id = uuid4()

        await logger.log(
            action=AuditAction.AGENT_CREATED,
            actor_id=uuid4(),
            resource_id=resource_id,
            details={},
        )
        await logger.log(
            action=AuditAction.AGENT_DELETED,
            actor_id=uuid4(),
            resource_id=uuid4(),
            details={},
        )

        entries = await logger.query(action=AuditAction.AGENT_CREATED)

        assert len(entries) >= 1
        assert all(e.action == AuditAction.AGENT_CREATED for e in entries)

    @pytest.mark.asyncio
    async def test_query_with_pagination(self, logger):
        """Test querying with pagination."""
        resource_id = uuid4()

        for i in range(10):
            await logger.log(
                action=AuditAction.AGENT_UPDATED,
                actor_id=uuid4(),
                resource_id=resource_id,
                details={"update": i},
            )

        page1 = await logger.query(resource_id=resource_id, limit=5, offset=0)
        page2 = await logger.query(resource_id=resource_id, limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5
        # Ensure different entries
        page1_ids = {e.id for e in page1}
        page2_ids = {e.id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)
