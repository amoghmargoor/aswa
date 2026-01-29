"""Tests for registry classes."""

import pytest

from aswa_agents.core.registry import AgentRegistry
from aswa_agents.actions.registry import ActionBlockRegistry
from aswa_agents.connectors.registry import ConnectorRegistry
from aswa_agents.core.base import Agent
from aswa_agents.core.models import Action, ActionContext, ActionResult, TriggerData
from aswa_agents.core.types import ActionType, ActionStatus, TriggerType


class MockAction(Action):
    """Mock action for testing."""
    pass


class TestAgentRegistry:
    """Test AgentRegistry class."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear registry before and after each test."""
        AgentRegistry.clear()
        yield
        AgentRegistry.clear()

    def test_initialize(self):
        """Test registry initialization."""
        AgentRegistry.initialize()
        assert AgentRegistry.is_initialized()

    def test_register_and_get(self):
        """Test registering and retrieving agents."""
        @AgentRegistry.register
        class DummyAgent(Agent[MockAction]):
            @property
            def supported_trigger_types(self) -> list[str]:
                return ["manual"]

            @property
            def required_permissions(self) -> list[str]:
                return []

            async def should_trigger(self, trigger, context):
                return True

            async def plan_actions(self, trigger, context):
                return []

            async def execute(self, action, context):
                return ActionResult(action_id=action.id, status=ActionStatus.COMPLETED)

        assert AgentRegistry.get_agent_class("DummyAgent") == DummyAgent

    def test_get_nonexistent(self):
        """Test getting non-existent agent."""
        AgentRegistry.initialize()
        assert AgentRegistry.get_agent_class("nonexistent") is None

    def test_list_agents(self):
        """Test listing registered agents."""
        @AgentRegistry.register
        class TestAgent(Agent[MockAction]):
            @property
            def supported_trigger_types(self) -> list[str]:
                return ["manual"]

            @property
            def required_permissions(self) -> list[str]:
                return []

            async def should_trigger(self, trigger, context):
                return True

            async def plan_actions(self, trigger, context):
                return []

            async def execute(self, action, context):
                return ActionResult(action_id=action.id, status=ActionStatus.COMPLETED)

        agents = AgentRegistry.list_agents()
        assert any(a["name"] == "TestAgent" for a in agents)


class TestActionBlockRegistry:
    """Test ActionBlockRegistry class."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear registry before and after each test."""
        ActionBlockRegistry.clear()
        yield
        ActionBlockRegistry.clear()

    def test_initialize(self):
        """Test registry initialization."""
        ActionBlockRegistry.initialize()
        assert ActionBlockRegistry.is_initialized()

    def test_register_and_get(self):
        """Test registering and retrieving blocks."""
        ActionBlockRegistry.initialize()

        class DummyBlock:
            pass

        ActionBlockRegistry.register("dummy_block", DummyBlock)
        assert ActionBlockRegistry.get("dummy_block") == DummyBlock

    def test_list_blocks(self):
        """Test listing registered blocks."""
        ActionBlockRegistry.initialize()

        class SummarizeBlock:
            pass

        ActionBlockRegistry.register("summarize", SummarizeBlock)
        blocks = ActionBlockRegistry.list_blocks()
        assert "summarize" in blocks


class TestConnectorRegistry:
    """Test ConnectorRegistry class."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear registry before and after each test."""
        ConnectorRegistry.clear()
        yield
        ConnectorRegistry.clear()

    def test_initialize(self):
        """Test registry initialization."""
        ConnectorRegistry.initialize()

    def test_register_and_get(self):
        """Test registering and retrieving connectors."""
        ConnectorRegistry.initialize()

        class SlackConnector:
            pass

        ConnectorRegistry.register("slack", SlackConnector)
        assert ConnectorRegistry.get("slack") == SlackConnector

    def test_list_connectors(self):
        """Test listing registered connectors."""
        ConnectorRegistry.initialize()

        class JiraConnector:
            pass

        ConnectorRegistry.register("jira", JiraConnector)
        connectors = ConnectorRegistry.list_connectors()
        assert "jira" in connectors
