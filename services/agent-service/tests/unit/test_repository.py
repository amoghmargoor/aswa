"""Tests for repository classes."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_agents.persistence.repository import (
    AgentRepository,
    DBExecutionRepository,
    DBActionRepository,
    ExecutionRepository,
    ActionRepository,
)
from aswa_agents.persistence.models import AgentModel, ExecutionModel, ActionModel
from aswa_agents.api.schemas import (
    AgentCreate,
    AgentUpdate,
    AgentDefinition,
    TriggerConfig,
    ActionConfig,
)
from aswa_agents.core.models import ExecutionResult, TriggerData, ActionResult, Action
from aswa_agents.core.types import ActionStatus, TriggerType, ActionType


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def sample_agent_create():
    """Create sample agent data."""
    return AgentCreate(
        name="test-agent",
        display_name="Test Agent",
        description="A test agent",
        definition=AgentDefinition(
            trigger=TriggerConfig(type="manual"),
            actions=[ActionConfig(id="action1", type="log")],
        ),
        tags=["test"],
    )


class TestAgentRepository:
    """Test AgentRepository class."""

    @pytest.mark.asyncio
    async def test_create_agent(self, mock_session, sample_agent_create):
        """Test creating an agent."""
        repo = AgentRepository(mock_session)

        # Mock the add to capture the agent
        added_agent = None
        def capture_add(agent):
            nonlocal added_agent
            added_agent = agent
        mock_session.add = capture_add

        await repo.create(
            tenant_id="test-tenant",
            data=sample_agent_create,
            created_by="test-user",
        )

        assert added_agent is not None
        assert added_agent.name == "test-agent"
        assert added_agent.tenant_id == "test-tenant"

    @pytest.mark.asyncio
    async def test_get_agent(self, mock_session):
        """Test getting an agent by ID."""
        agent_id = uuid4()
        mock_agent = MagicMock(spec=AgentModel)
        mock_agent.id = agent_id
        mock_agent.name = "test"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.get(agent_id, "test-tenant")

        assert result is not None
        assert result.id == agent_id

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_session):
        """Test getting non-existent agent."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.get(uuid4(), "test-tenant")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_agents(self, mock_session):
        """Test listing agents."""
        mock_agents = [MagicMock(spec=AgentModel) for _ in range(3)]

        # Mock count query
        mock_session.scalar.return_value = 3

        # Mock list query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_agents
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        agents, total = await repo.list("test-tenant")

        assert len(agents) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_delete_agent(self, mock_session):
        """Test deleting an agent."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.delete(uuid4(), "test-tenant")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, mock_session):
        """Test deleting non-existent agent."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.delete(uuid4(), "test-tenant")

        assert result is False


class TestDBExecutionRepository:
    """Test DBExecutionRepository class."""

    @pytest.mark.asyncio
    async def test_save_execution(self, mock_session):
        """Test saving an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )

        added_model = None
        def capture_add(model):
            nonlocal added_model
            added_model = model
        mock_session.add = capture_add

        repo = DBExecutionRepository(mock_session)
        await repo.save(execution)

        assert added_model is not None
        assert added_model.id == execution.execution_id

    @pytest.mark.asyncio
    async def test_update_execution(self, mock_session):
        """Test updating an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.COMPLETED,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        repo = DBExecutionRepository(mock_session)
        await repo.update(execution)

        mock_session.execute.assert_called_once()


class TestDBActionRepository:
    """Test DBActionRepository class."""

    @pytest.mark.asyncio
    async def test_update_status(self, mock_session):
        """Test updating action status."""
        repo = DBActionRepository(mock_session)
        await repo.update_status(uuid4(), ActionStatus.EXECUTING)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_action(self, mock_session):
        """Test approving an action."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = DBActionRepository(mock_session)
        result = await repo.approve(uuid4(), "approver", "Looks good")

        assert result is True

    @pytest.mark.asyncio
    async def test_reject_action(self, mock_session):
        """Test rejecting an action."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = DBActionRepository(mock_session)
        result = await repo.reject(uuid4(), "reviewer", "Not appropriate")

        assert result is True


class TestInMemoryActionRepository:
    """Test in-memory ActionRepository class."""

    @pytest.fixture
    def action_repo(self):
        return ActionRepository()

    @pytest.mark.asyncio
    async def test_save_and_get(self, action_repo):
        """Test saving and getting an action."""
        action = Action(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=0.9,
        )
        context = MagicMock()
        context.model_dump = MagicMock(return_value={})

        await action_repo.save(action, "test-agent", context)

        result = await action_repo.get(action.id)
        assert result is not None
        assert result["type"] == "custom"
        assert result["target_system"] == "test"

    @pytest.mark.asyncio
    async def test_update_status(self, action_repo):
        """Test updating action status."""
        action = Action(
            type=ActionType.CUSTOM,
            target_system="test",
        )
        context = MagicMock()
        context.model_dump = MagicMock(return_value={})

        await action_repo.save(action, "test-agent", context)
        await action_repo.update_status(action.id, ActionStatus.EXECUTING)

        result = await action_repo.get(action.id)
        assert result["status"] == "executing"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, action_repo):
        """Test getting non-existent action."""
        result = await action_repo.get(uuid4())
        assert result is None


class TestInMemoryExecutionRepository:
    """Test in-memory ExecutionRepository class."""

    @pytest.fixture
    def execution_repo(self):
        return ExecutionRepository()

    @pytest.mark.asyncio
    async def test_save_and_get(self, execution_repo):
        """Test saving and getting an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )

        await execution_repo.save(execution)

        result = await execution_repo.get(execution.execution_id)
        assert result is not None
        assert result.tenant_id == "test-tenant"
        assert result.status == ActionStatus.PENDING

    @pytest.mark.asyncio
    async def test_update(self, execution_repo):
        """Test updating an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )

        await execution_repo.save(execution)

        execution.status = ActionStatus.COMPLETED
        await execution_repo.update(execution)

        result = await execution_repo.get(execution.execution_id)
        assert result.status == ActionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, execution_repo):
        """Test listing executions by tenant."""
        for i in range(5):
            execution = ExecutionResult(
                execution_id=uuid4(),
                agent_id=uuid4(),
                tenant_id="test-tenant",
                status=ActionStatus.PENDING,
                trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
                started_at=datetime.now(timezone.utc),
            )
            await execution_repo.save(execution)

        executions, total = await execution_repo.list_by_tenant("test-tenant")
        assert total == 5
        assert len(executions) == 5

    @pytest.mark.asyncio
    async def test_delete(self, execution_repo):
        """Test deleting an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )

        await execution_repo.save(execution)
        deleted = await execution_repo.delete(execution.execution_id)

        assert deleted is True
        result = await execution_repo.get(execution.execution_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, execution_repo):
        """Test deleting non-existent execution."""
        deleted = await execution_repo.delete(uuid4())
        assert deleted is False
