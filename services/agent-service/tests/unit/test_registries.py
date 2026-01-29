"""Tests for registry classes."""

import pytest

from aswa_agents.core.registry import AgentRegistry
from aswa_agents.actions.registry import ActionBlockRegistry
from aswa_agents.connectors.registry import ConnectorRegistry


class TestAgentRegistry:
    """Test AgentRegistry class."""

    def test_initialize(self):
        """Test registry initialization."""
        AgentRegistry.initialize()
        assert AgentRegistry.is_initialized()

    def test_register_and_get(self):
        """Test registering and retrieving agents."""
        AgentRegistry.initialize()

        class DummyAgent:
            pass

        AgentRegistry.register("dummy", DummyAgent)
        assert AgentRegistry.get("dummy") == DummyAgent

    def test_get_nonexistent(self):
        """Test getting non-existent agent."""
        AgentRegistry.initialize()
        assert AgentRegistry.get("nonexistent") is None

    def test_list_agents(self):
        """Test listing registered agents."""
        AgentRegistry.initialize()

        class TestAgent:
            pass

        AgentRegistry.register("test", TestAgent)
        agents = AgentRegistry.list_agents()
        assert "test" in agents


class TestActionBlockRegistry:
    """Test ActionBlockRegistry class."""

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
