"""Tests for API schemas."""

import pytest
from pydantic import ValidationError

from aswa_agents.api.schemas import (
    AgentCreate,
    AgentDefinition,
    TriggerConfig,
    ActionConfig,
    ApprovalConfig,
    ApprovalMode,
    AgentStatus,
    ExecutionStatus,
)


class TestAgentSchemas:
    """Test agent-related schemas."""

    def test_trigger_config_creation(self):
        """Test TriggerConfig creation."""
        trigger = TriggerConfig(
            type="email_received",
            config={"inbox": "support@example.com"},
        )

        assert trigger.type == "email_received"
        assert trigger.config["inbox"] == "support@example.com"

    def test_trigger_config_defaults(self):
        """Test TriggerConfig default values."""
        trigger = TriggerConfig(type="manual")

        assert trigger.type == "manual"
        assert trigger.config == {}

    def test_action_config_creation(self):
        """Test ActionConfig creation."""
        action = ActionConfig(
            id="summarize_1",
            type="summarize",
            config={"max_length": 200},
            depends_on=[],
        )

        assert action.id == "summarize_1"
        assert action.type == "summarize"
        assert action.config["max_length"] == 200

    def test_action_config_defaults(self):
        """Test ActionConfig default values."""
        action = ActionConfig(id="action_1", type="log")

        assert action.depends_on == []
        assert action.config == {}

    def test_approval_config_defaults(self):
        """Test ApprovalConfig default values."""
        approval = ApprovalConfig()

        assert approval.mode == ApprovalMode.REVIEW
        assert approval.timeout_hours == 24
        assert approval.reviewers == []

    def test_agent_definition_creation(self):
        """Test AgentDefinition creation."""
        definition = AgentDefinition(
            trigger=TriggerConfig(type="webhook"),
            actions=[
                ActionConfig(id="action_1", type="summarize"),
            ],
        )

        assert definition.trigger.type == "webhook"
        assert len(definition.actions) == 1
        assert definition.approval.mode == ApprovalMode.REVIEW
        assert definition.conditions == []
        assert definition.variables == []

    def test_agent_definition_with_conditions(self):
        """Test AgentDefinition with conditions."""
        definition = AgentDefinition(
            trigger=TriggerConfig(type="email_received"),
            conditions=[{"field": "subject", "operator": "contains", "value": "urgent"}],
            actions=[ActionConfig(id="a1", type="notify")],
        )

        assert len(definition.conditions) == 1

    def test_agent_create_validation(self):
        """Test AgentCreate validation."""
        agent = AgentCreate(
            name="test-agent",
            display_name="Test Agent",
            description="A test agent",
            definition=AgentDefinition(
                trigger=TriggerConfig(type="manual"),
                actions=[ActionConfig(id="a1", type="log")],
            ),
            tags=["test"],
        )

        assert agent.name == "test-agent"
        assert len(agent.tags) == 1

    def test_agent_create_name_validation_empty(self):
        """Test name field validation for empty string."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="",  # Empty name should fail
                display_name="Test",
                definition=AgentDefinition(
                    trigger=TriggerConfig(type="manual"),
                    actions=[],
                ),
            )

    def test_agent_create_name_validation_too_long(self):
        """Test name field validation for too long string."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="a" * 101,  # More than 100 characters should fail
                display_name="Test",
                definition=AgentDefinition(
                    trigger=TriggerConfig(type="manual"),
                    actions=[],
                ),
            )


class TestEnums:
    """Test enum values."""

    def test_agent_status_values(self):
        """Test AgentStatus enum values."""
        assert AgentStatus.DRAFT.value == "draft"
        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.ARCHIVED.value == "archived"

    def test_approval_mode_values(self):
        """Test ApprovalMode enum values."""
        assert ApprovalMode.AUTO.value == "auto"
        assert ApprovalMode.NOTIFY.value == "notify"
        assert ApprovalMode.REVIEW.value == "review"
        assert ApprovalMode.MANUAL.value == "manual"

    def test_execution_status_values(self):
        """Test ExecutionStatus enum values."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"
