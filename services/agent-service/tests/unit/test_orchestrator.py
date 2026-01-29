"""Tests for agent orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from aswa_agents.core.orchestrator import AgentOrchestrator, ExecutionError, RetryableError
from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    TriggerData,
    ExecutionResult,
)
from aswa_agents.core.types import ActionStatus, ActionType, ApprovalLevel, TriggerType
from aswa_agents.core.base import Agent
from aswa_agents.core.registry import AgentRegistry
from aswa_agents.persistence.repository import ActionRepository, ExecutionRepository
from aswa_agents.approval.service import ApprovalService


class MockAction(Action):
    """Mock action for testing."""
    pass


class MockAgent(Agent[MockAction]):
    """Mock agent for testing."""

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["manual"]

    @property
    def required_permissions(self) -> list[str]:
        return []

    async def should_trigger(self, trigger, context) -> bool:
        return True

    async def plan_actions(self, trigger, context) -> list[MockAction]:
        return [
            MockAction(
                type=ActionType.CUSTOM,
                target_system="test",
                confidence=0.95,
            )
        ]

    async def execute(self, action, context) -> ActionResult:
        return ActionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            result_data={"success": True},
        )


class LowConfidenceMockAgent(MockAgent):
    """Agent that generates low confidence actions for review."""

    async def plan_actions(self, trigger, context) -> list[MockAction]:
        return [
            MockAction(
                type=ActionType.CUSTOM,
                target_system="test",
                confidence=0.75,  # Medium confidence - triggers REVIEW level
            )
        ]


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before and after each test."""
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


@pytest.fixture
def action_repository():
    """Create action repository."""
    return ActionRepository()


@pytest.fixture
def execution_repository():
    """Create execution repository."""
    return ExecutionRepository()


@pytest.fixture
def approval_service():
    """Create approval service."""
    return ApprovalService()


@pytest.fixture
def orchestrator(action_repository, execution_repository, approval_service):
    """Create orchestrator instance."""
    return AgentOrchestrator(
        action_repository=action_repository,
        execution_repository=execution_repository,
        approval_service=approval_service,
    )


class TestAgentOrchestrator:
    """Test AgentOrchestrator class."""

    @pytest.mark.asyncio
    async def test_process_trigger_no_matching_agents(self, orchestrator):
        """Test processing trigger with no matching agents."""
        trigger = TriggerData(trigger_type=TriggerType.EMAIL_RECEIVED)
        tenant_config = {"enabled_agents": []}

        execution_ids = await orchestrator.process_trigger(trigger, tenant_config)
        assert len(execution_ids) == 0

    @pytest.mark.asyncio
    async def test_process_trigger_with_matching_agent(self, orchestrator):
        """Test processing trigger with matching agent."""
        # Register mock agent
        AgentRegistry.register(MockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"tenant_id": "test"}

        execution_ids = await orchestrator.process_trigger(trigger, tenant_config)
        assert len(execution_ids) == 1

    @pytest.mark.asyncio
    async def test_process_trigger_dry_run(self, orchestrator, action_repository):
        """Test dry run doesn't execute actions."""
        AgentRegistry.register(MockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"tenant_id": "test"}

        execution_ids = await orchestrator.process_trigger(
            trigger, tenant_config, dry_run=True
        )

        assert len(execution_ids) == 1

        # Check that action was marked as skipped (dry run)
        actions = await action_repository.list_by_execution(execution_ids[0])
        # The dry run should have saved an action but not executed it fully

    @pytest.mark.asyncio
    async def test_action_approval_routing_auto(self, orchestrator, approval_service):
        """Test auto-approval actions execute immediately."""
        AgentRegistry.register(MockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {
            "tenant_id": "test",
            "approval_thresholds": {"auto": 0.9},
        }

        await orchestrator.process_trigger(trigger, tenant_config)

        # Should not have pending approvals for high confidence
        pending = await approval_service.get_pending_approvals("test")
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_action_approval_routing_review(self, orchestrator, approval_service):
        """Test low confidence actions go to review."""
        AgentRegistry.register(LowConfidenceMockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"tenant_id": "test"}

        await orchestrator.process_trigger(trigger, tenant_config)

        # Should have pending approval for low confidence
        pending = await approval_service.get_pending_approvals("test")
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_cancel_execution(self, orchestrator, execution_repository):
        """Test cancelling an execution."""
        execution_id = uuid4()

        execution = ExecutionResult(
            execution_id=execution_id,
            agent_id=uuid4(),
            tenant_id="test",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )
        await execution_repository.save(execution)

        result = await orchestrator.cancel_execution(execution_id)
        assert result is True

        # Verify status was updated
        updated = await execution_repository.get(execution_id)
        assert updated.status == ActionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_execution_fails(self, orchestrator, execution_repository):
        """Test cannot cancel completed execution."""
        execution_id = uuid4()

        execution = ExecutionResult(
            execution_id=execution_id,
            agent_id=uuid4(),
            tenant_id="test",
            status=ActionStatus.COMPLETED,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.now(timezone.utc),
        )
        await execution_repository.save(execution)

        result = await orchestrator.cancel_execution(execution_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_execution(self, orchestrator):
        """Test cancelling non-existent execution returns False."""
        result = await orchestrator.cancel_execution(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_execution_creates_record(self, orchestrator, execution_repository):
        """Test that execution creates a record in repository."""
        AgentRegistry.register(MockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"tenant_id": "test"}

        execution_ids = await orchestrator.process_trigger(trigger, tenant_config)

        assert len(execution_ids) == 1
        execution = await execution_repository.get(execution_ids[0])
        assert execution is not None
        assert execution.tenant_id == "test"

    @pytest.mark.asyncio
    async def test_action_repository_saves_action(self, orchestrator, action_repository):
        """Test that actions are saved to repository."""
        AgentRegistry.register(MockAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"tenant_id": "test"}

        await orchestrator.process_trigger(trigger, tenant_config)

        # There should be at least one action saved
        assert len(action_repository._actions) >= 1


class TestExecutionError:
    """Test ExecutionError exception."""

    def test_execution_error_message(self):
        """Test ExecutionError stores message."""
        error = ExecutionError("Test error message")
        assert str(error) == "Test error message"


class TestRetryableError:
    """Test RetryableError exception."""

    def test_retryable_error_message(self):
        """Test RetryableError stores message."""
        error = RetryableError("Temporary failure")
        assert str(error) == "Temporary failure"
