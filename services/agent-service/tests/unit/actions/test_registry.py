"""Tests for action registry."""

import pytest

from aswa_agents.actions.blocks.base import ActionBlock, ActionCategory, ActionContext
from aswa_agents.actions.blocks.registry import ActionRegistry, register_action


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry before each test."""
    ActionRegistry.clear()
    yield
    ActionRegistry.clear()


class TestActionRegistry:
    """Tests for ActionRegistry."""

    def test_initialize(self):
        """Test registry initialization."""
        ActionRegistry.initialize()

        # Should have registered actions
        assert len(ActionRegistry.get_all()) > 0

    def test_get_action(self):
        """Test getting action by type."""
        ActionRegistry.initialize()

        summarize = ActionRegistry.get("summarize")
        assert summarize is not None
        assert summarize.action_type == "summarize"

    def test_get_unknown_action(self):
        """Test getting unknown action type."""
        ActionRegistry.initialize()

        unknown = ActionRegistry.get("nonexistent_action")
        assert unknown is None

    def test_create_action(self):
        """Test creating action instance."""
        ActionRegistry.initialize()

        action = ActionRegistry.create(
            action_type="summarize",
            action_id="test_1",
            config={"style": "brief"},
        )

        assert action is not None
        assert action.action_id == "test_1"
        assert action.config["style"] == "brief"

    def test_create_unknown_action(self):
        """Test creating unknown action type raises error."""
        ActionRegistry.initialize()

        with pytest.raises(ValueError, match="Unknown action type"):
            ActionRegistry.create("nonexistent", "test_1", {})

    def test_get_by_category(self):
        """Test getting actions by category."""
        ActionRegistry.initialize()

        data_actions = ActionRegistry.get_by_category(ActionCategory.DATA)
        assert len(data_actions) > 0
        assert all(a.category == ActionCategory.DATA for a in data_actions)

        logic_actions = ActionRegistry.get_by_category(ActionCategory.LOGIC)
        assert len(logic_actions) > 0
        assert all(a.category == ActionCategory.LOGIC for a in logic_actions)

    def test_get_schema(self):
        """Test getting action schema."""
        ActionRegistry.initialize()

        schema = ActionRegistry.get_schema("summarize")
        assert schema is not None
        assert "style" in schema.properties

    def test_get_action_info(self):
        """Test getting action info."""
        ActionRegistry.initialize()

        info = ActionRegistry.get_action_info("summarize")
        assert info is not None
        assert info["type"] == "summarize"
        assert info["category"] == "data"
        assert info["display_name"] == "Summarize"
        assert "schema" in info

    def test_get_all_action_info(self):
        """Test getting all action info."""
        ActionRegistry.initialize()

        all_info = ActionRegistry.get_all_action_info()
        assert len(all_info) > 0
        assert all(info["type"] for info in all_info)

    def test_get_catalog(self):
        """Test getting action catalog."""
        ActionRegistry.initialize()

        catalog = ActionRegistry.get_catalog()
        assert "data" in catalog
        assert "integration" in catalog
        assert "logic" in catalog

        assert len(catalog["data"]) > 0
        assert len(catalog["integration"]) > 0
        assert len(catalog["logic"]) > 0

    def test_clear(self):
        """Test clearing registry."""
        ActionRegistry.initialize()
        assert len(ActionRegistry.get_all()) > 0

        ActionRegistry.clear()
        # Registry is lazy, so it will re-initialize
        # But _initialized flag should be False


class TestRegisterDecorator:
    """Tests for register_action decorator."""

    def test_register_custom_action(self):
        """Test registering custom action with decorator."""

        @register_action
        class CustomAction(ActionBlock):
            action_type = "custom_test"
            category = ActionCategory.UTILITY
            display_name = "Custom Test"
            description = "A custom test action"

            async def execute(self, context: ActionContext):
                return self._create_result(status="success", output={"test": True})

        action_class = ActionRegistry.get("custom_test")
        assert action_class is not None
        assert action_class.action_type == "custom_test"

    def test_register_overwrites_existing(self):
        """Test registering action overwrites existing."""
        ActionRegistry.initialize()

        original = ActionRegistry.get("summarize")

        @register_action
        class ReplacementSummarize(ActionBlock):
            action_type = "summarize"
            category = ActionCategory.DATA
            display_name = "Replacement Summarize"
            description = "Replaced summarize"

            async def execute(self, context: ActionContext):
                pass

        new = ActionRegistry.get("summarize")
        assert new != original
        assert new.display_name == "Replacement Summarize"


class TestBuiltinActions:
    """Tests for built-in actions registration."""

    def test_data_actions_registered(self):
        """Test data actions are registered."""
        ActionRegistry.initialize()

        assert ActionRegistry.get("summarize") is not None
        assert ActionRegistry.get("extract") is not None
        assert ActionRegistry.get("transform") is not None
        assert ActionRegistry.get("aggregate") is not None

    def test_integration_actions_registered(self):
        """Test integration actions are registered."""
        ActionRegistry.initialize()

        assert ActionRegistry.get("send_slack") is not None
        assert ActionRegistry.get("send_email") is not None
        assert ActionRegistry.get("create_ticket") is not None
        assert ActionRegistry.get("webhook") is not None

    def test_logic_actions_registered(self):
        """Test logic actions are registered."""
        ActionRegistry.initialize()

        assert ActionRegistry.get("filter") is not None
        assert ActionRegistry.get("branch") is not None
        assert ActionRegistry.get("loop") is not None
        assert ActionRegistry.get("delay") is not None
        assert ActionRegistry.get("retry") is not None
