"""Tests for Agent base class."""

import pytest
from uuid import uuid4

from aswa_agents.core.base import Agent
from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    TriggerData,
)
from aswa_agents.core.types import ActionType, ActionStatus, ApprovalLevel, TriggerType


class MockAction(Action):
    """Mock action for testing."""
    pass


class MockAgent(Agent[MockAction]):
    """Mock agent for testing."""

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["manual", "webhook"]

    @property
    def required_permissions(self) -> list[str]:
        return ["jira:write", "slack:post"]

    async def should_trigger(self, trigger: TriggerData, context: ActionContext) -> bool:
        return trigger.trigger_type.value in self.supported_trigger_types

    async def plan_actions(self, trigger: TriggerData, context: ActionContext) -> list[MockAction]:
        return [
            MockAction(
                type=ActionType.CUSTOM,
                target_system="test",
                confidence=0.9,
            )
        ]

    async def execute(self, action: MockAction, context: ActionContext) -> ActionResult:
        return ActionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            result_data={"test": True},
        )


class TestAgentBase:
    """Test Agent base class."""

    @pytest.fixture
    def agent(self):
        return MockAgent()

    @pytest.fixture
    def context(self):
        return ActionContext(
            agent_id=uuid4(),
            agent_name="MockAgent",
            tenant_id="test-tenant",
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
        )

    def test_agent_name(self, agent):
        """Test agent name property."""
        assert agent.name == "MockAgent"

    def test_agent_version(self, agent):
        """Test agent version property."""
        assert agent.version == "1.0.0"

    def test_agent_description(self, agent):
        """Test agent description property."""
        assert "Mock agent for testing" in agent.description

    def test_required_connectors(self, agent):
        """Test required connectors extraction."""
        connectors = agent.required_connectors
        assert "jira" in connectors
        assert "slack" in connectors

    def test_agent_repr(self, agent):
        """Test agent repr."""
        assert "MockAgent" in repr(agent)
        assert "version=1.0.0" in repr(agent)

    def test_get_config(self, agent):
        """Test get_config method."""
        agent.config = {"key": "value"}
        assert agent.get_config("key") == "value"
        assert agent.get_config("missing", "default") == "default"

    @pytest.mark.asyncio
    async def test_should_trigger(self, agent, context):
        """Test should_trigger logic."""
        assert await agent.should_trigger(context.trigger_data, context)

        context.trigger_data.trigger_type = TriggerType.EMAIL_RECEIVED
        assert not await agent.should_trigger(context.trigger_data, context)

    @pytest.mark.asyncio
    async def test_plan_actions(self, agent, context):
        """Test action planning."""
        actions = await agent.plan_actions(context.trigger_data, context)
        assert len(actions) == 1
        assert actions[0].type == ActionType.CUSTOM

    @pytest.mark.asyncio
    async def test_execute(self, agent, context):
        """Test action execution."""
        actions = await agent.plan_actions(context.trigger_data, context)
        result = await agent.execute(actions[0], context)
        assert result.is_success
        assert result.result_data["test"] is True

    @pytest.mark.asyncio
    async def test_validate_action(self, agent, context):
        """Test default validate_action returns True."""
        action = MockAction(type=ActionType.CUSTOM, target_system="test")
        assert await agent.validate_action(action, context)

    def test_approval_level_high_confidence(self, agent, context):
        """Test approval level for high confidence."""
        action = MockAction(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=0.96,
        )
        level = agent.get_approval_level(action, context)
        assert level == ApprovalLevel.AUTO

    def test_approval_level_medium_confidence(self, agent, context):
        """Test approval level for medium confidence."""
        action = MockAction(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=0.87,
        )
        level = agent.get_approval_level(action, context)
        assert level == ApprovalLevel.NOTIFY

    def test_approval_level_low_confidence(self, agent, context):
        """Test approval level for low confidence."""
        action = MockAction(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=0.72,
        )
        level = agent.get_approval_level(action, context)
        assert level == ApprovalLevel.REVIEW

    def test_approval_level_very_low_confidence(self, agent, context):
        """Test approval level for very low confidence."""
        action = MockAction(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=0.5,
        )
        level = agent.get_approval_level(action, context)
        assert level == ApprovalLevel.MANUAL

    def test_approval_level_dry_run(self, agent, context):
        """Test approval level in dry run mode."""
        context.dry_run = True
        action = MockAction(
            type=ActionType.CUSTOM,
            target_system="test",
            confidence=1.0,
        )
        level = agent.get_approval_level(action, context)
        assert level == ApprovalLevel.MANUAL

    def test_approval_level_high_risk_action(self, agent, context):
        """Test approval level for high-risk action types."""
        action = MockAction(
            type=ActionType.SEND_EMAIL,
            target_system="email",
            confidence=0.95,
        )
        level = agent.get_approval_level(action, context)
        # High-risk actions get at least NOTIFY even with high confidence
        assert level in (ApprovalLevel.NOTIFY, ApprovalLevel.REVIEW)
