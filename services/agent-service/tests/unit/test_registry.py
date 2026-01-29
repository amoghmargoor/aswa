"""Comprehensive tests for AgentRegistry."""

import pytest
from uuid import uuid4

from aswa_agents.core.registry import AgentRegistry
from aswa_agents.core.base import Agent
from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    TriggerData,
)
from aswa_agents.core.types import (
    ActionType,
    ActionStatus,
    TriggerType,
)


class MockAction(Action):
    """Mock action for testing."""
    pass


class TestAgentForRegistry(Agent[MockAction]):
    """Test agent for registry tests."""

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["manual", "webhook", "document_ingested"]

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


class AnotherTestAgent(Agent[MockAction]):
    """Another test agent for registry tests."""

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["email_received", "scheduled"]

    @property
    def required_permissions(self) -> list[str]:
        return ["email:read", "zendesk:write"]

    async def should_trigger(self, trigger: TriggerData, context: ActionContext) -> bool:
        return trigger.trigger_type.value in self.supported_trigger_types

    async def plan_actions(self, trigger: TriggerData, context: ActionContext) -> list[MockAction]:
        return []

    async def execute(self, action: MockAction, context: ActionContext) -> ActionResult:
        return ActionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
        )


class TestAgentRegistry:
    """Test AgentRegistry singleton."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear registry before and after each test."""
        AgentRegistry.clear()
        yield
        AgentRegistry.clear()

    def test_singleton_pattern(self):
        """Test that AgentRegistry is a singleton."""
        reg1 = AgentRegistry()
        reg2 = AgentRegistry()
        assert reg1 is reg2

    def test_initialize(self):
        """Test registry initialization."""
        AgentRegistry.initialize()
        assert AgentRegistry.is_initialized()

    def test_initialize_idempotent(self):
        """Test that initialize can be called multiple times."""
        AgentRegistry.initialize()
        AgentRegistry.initialize()  # Should not raise
        assert AgentRegistry.is_initialized()

    def test_register_decorator(self):
        """Test registering agent via decorator."""
        @AgentRegistry.register
        class DecoratorTestAgent(Agent[MockAction]):
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

        assert AgentRegistry.get_agent_class("DecoratorTestAgent") is DecoratorTestAgent

    def test_register_overwrites_existing(self):
        """Test that registering same name overwrites."""
        @AgentRegistry.register
        class DuplicateAgent(Agent[MockAction]):
            version_number = 1

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

        # Register another class with same name (simulating re-registration)
        class DuplicateAgent2(Agent[MockAction]):
            version_number = 2

            @property
            def supported_trigger_types(self) -> list[str]:
                return ["webhook"]

            @property
            def required_permissions(self) -> list[str]:
                return []

            async def should_trigger(self, trigger, context):
                return True

            async def plan_actions(self, trigger, context):
                return []

            async def execute(self, action, context):
                return ActionResult(action_id=action.id, status=ActionStatus.COMPLETED)

        # Manually rename to simulate name collision
        DuplicateAgent2.__name__ = "DuplicateAgent"
        AgentRegistry.register(DuplicateAgent2)

        agent_class = AgentRegistry.get_agent_class("DuplicateAgent")
        assert agent_class.version_number == 2

    def test_unregister(self):
        """Test unregistering an agent."""
        AgentRegistry.register(TestAgentForRegistry)
        assert AgentRegistry.get_agent_class("TestAgentForRegistry") is not None

        result = AgentRegistry.unregister("TestAgentForRegistry")
        assert result is True
        assert AgentRegistry.get_agent_class("TestAgentForRegistry") is None

    def test_unregister_nonexistent(self):
        """Test unregistering non-existent agent returns False."""
        result = AgentRegistry.unregister("NonExistentAgent")
        assert result is False

    def test_get_agent_class(self):
        """Test getting agent class by name."""
        AgentRegistry.register(TestAgentForRegistry)
        agent_class = AgentRegistry.get_agent_class("TestAgentForRegistry")
        assert agent_class is TestAgentForRegistry

    def test_get_agent_class_not_found(self):
        """Test getting non-existent agent returns None."""
        result = AgentRegistry.get_agent_class("NonExistentAgent")
        assert result is None

    def test_get_agent_instantiated(self):
        """Test getting instantiated agent."""
        AgentRegistry.register(TestAgentForRegistry)
        agent = AgentRegistry.get_agent("TestAgentForRegistry", {"key": "value"})
        assert isinstance(agent, TestAgentForRegistry)
        assert agent.config == {"key": "value"}

    def test_get_agent_not_found(self):
        """Test getting non-existent agent returns None."""
        result = AgentRegistry.get_agent("NonExistentAgent")
        assert result is None

    def test_get_all_agents(self):
        """Test getting all registered agents."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.register(AnotherTestAgent)

        all_agents = AgentRegistry.get_all_agents()
        assert "TestAgentForRegistry" in all_agents
        assert "AnotherTestAgent" in all_agents
        assert len(all_agents) == 2

    def test_list_agents_with_metadata(self):
        """Test listing agents with metadata."""
        AgentRegistry.register(TestAgentForRegistry)

        agents = AgentRegistry.list_agents()
        assert len(agents) == 1

        agent_info = agents[0]
        assert agent_info["name"] == "TestAgentForRegistry"
        assert agent_info["version"] == "1.0.0"
        assert "manual" in agent_info["supported_trigger_types"]
        assert "jira:write" in agent_info["required_permissions"]
        assert "jira" in agent_info["required_connectors"]

    def test_find_agents_for_trigger_basic(self):
        """Test finding agents for a trigger."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.register(AnotherTestAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {}

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)

        # Only TestAgentForRegistry supports manual trigger
        assert len(matching) == 1
        agent_class, config = matching[0]
        assert agent_class is TestAgentForRegistry

    def test_find_agents_for_trigger_with_enabled_agents(self):
        """Test finding agents respects enabled_agents config."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.register(AnotherTestAgent)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {
            "enabled_agents": ["AnotherTestAgent"]  # Exclude TestAgentForRegistry
        }

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)

        # TestAgentForRegistry is not in enabled list
        assert len(matching) == 0

    def test_find_agents_for_trigger_with_disabled_agents(self):
        """Test finding agents respects disabled_agents config."""
        AgentRegistry.register(TestAgentForRegistry)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {
            "disabled_agents": ["TestAgentForRegistry"]
        }

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        assert len(matching) == 0

    def test_find_agents_for_trigger_with_agent_specific_config(self):
        """Test finding agents with agent-specific config."""
        AgentRegistry.register(TestAgentForRegistry)

        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {
            "agent_TestAgentForRegistry": {"enabled": False}
        }

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        assert len(matching) == 0

    def test_find_agents_by_permission(self):
        """Test finding agents by permission."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.register(AnotherTestAgent)

        jira_agents = AgentRegistry.find_agents_by_permission("jira:write")
        assert len(jira_agents) == 1
        assert jira_agents[0] is TestAgentForRegistry

        email_agents = AgentRegistry.find_agents_by_permission("email:read")
        assert len(email_agents) == 1
        assert email_agents[0] is AnotherTestAgent

    def test_find_agents_by_connector(self):
        """Test finding agents by connector."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.register(AnotherTestAgent)

        jira_agents = AgentRegistry.find_agents_by_connector("jira")
        assert len(jira_agents) == 1
        assert jira_agents[0] is TestAgentForRegistry

        slack_agents = AgentRegistry.find_agents_by_connector("slack")
        assert len(slack_agents) == 1
        assert slack_agents[0] is TestAgentForRegistry

    def test_validate_agent_config_unknown_agent(self):
        """Test validating config for unknown agent."""
        is_valid, errors = AgentRegistry.validate_agent_config("UnknownAgent", {})
        assert is_valid is False
        assert "Unknown agent: UnknownAgent" in errors

    def test_validate_agent_config_valid(self):
        """Test validating valid config."""
        AgentRegistry.register(TestAgentForRegistry)

        is_valid, errors = AgentRegistry.validate_agent_config(
            "TestAgentForRegistry",
            {"some_key": "some_value"},
        )
        assert is_valid is True
        assert len(errors) == 0

    def test_count(self):
        """Test agent count."""
        assert AgentRegistry.count() == 0

        AgentRegistry.register(TestAgentForRegistry)
        assert AgentRegistry.count() == 1

        AgentRegistry.register(AnotherTestAgent)
        assert AgentRegistry.count() == 2

    def test_clear(self):
        """Test clearing the registry."""
        AgentRegistry.register(TestAgentForRegistry)
        AgentRegistry.initialize()

        AgentRegistry.clear()

        assert AgentRegistry.count() == 0
        assert AgentRegistry.is_initialized() is False
