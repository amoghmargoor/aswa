"""Tests for action blocks base classes."""

import pytest
from uuid import uuid4

from aswa_agents.actions.blocks.base import (
    ActionBlock,
    ActionCategory,
    ActionContext,
    ActionResult,
    ActionSchema,
    ActionStatus,
)


class TestActionContext:
    """Tests for ActionContext."""

    def test_create_context(self):
        """Test creating action context."""
        context = ActionContext(
            agent_id=uuid4(),
            run_id=uuid4(),
            tenant_id=uuid4(),
            trigger_data={"subject": "Test"},
            variables={"custom_var": "value"},
            previous_outputs={"action_1": {"summary": "Test summary"}},
            secrets={"API_KEY": "secret123"},
        )

        assert context.trigger_data["subject"] == "Test"
        assert context.variables["custom_var"] == "value"

    def test_get_variable(self):
        """Test getting variable from context."""
        context = ActionContext(
            agent_id=uuid4(),
            run_id=uuid4(),
            tenant_id=uuid4(),
            variables={"name": "test"},
        )

        assert context.get_variable("name") == "test"
        assert context.get_variable("missing", "default") == "default"

    def test_get_previous_output(self):
        """Test getting previous action output."""
        context = ActionContext(
            agent_id=uuid4(),
            run_id=uuid4(),
            tenant_id=uuid4(),
            previous_outputs={"summarize_1": {"summary": "Result"}},
        )

        assert context.get_previous_output("summarize_1") == {"summary": "Result"}
        assert context.get_previous_output("missing") is None

    def test_get_secret(self):
        """Test getting secret."""
        context = ActionContext(
            agent_id=uuid4(),
            run_id=uuid4(),
            tenant_id=uuid4(),
            secrets={"SLACK_TOKEN": "xoxb-test"},
        )

        assert context.get_secret("SLACK_TOKEN") == "xoxb-test"
        assert context.get_secret("MISSING") is None


class TestActionResult:
    """Tests for ActionResult."""

    def test_create_result(self):
        """Test creating action result."""
        result = ActionResult(
            action_id="action_1",
            status=ActionStatus.SUCCESS,
            output={"summary": "Test"},
            duration_ms=100.5,
        )

        assert result.action_id == "action_1"
        assert result.status == ActionStatus.SUCCESS
        assert result.output == {"summary": "Test"}
        assert result.duration_ms == 100.5

    def test_failed_result(self):
        """Test creating failed result."""
        result = ActionResult(
            action_id="action_1",
            status=ActionStatus.FAILED,
            error="Something went wrong",
        )

        assert result.status == ActionStatus.FAILED
        assert result.error == "Something went wrong"
        assert result.output is None


class TestActionSchema:
    """Tests for ActionSchema."""

    def test_validate_config_success(self):
        """Test validating config successfully."""
        schema = ActionSchema(
            type="object",
            required=["channel"],
            properties={
                "channel": {"type": "string"},
                "message": {"type": "string"},
            },
        )

        errors = schema.validate_config({"channel": "#general", "message": "Hello"})
        assert len(errors) == 0

    def test_validate_config_missing_required(self):
        """Test validation fails for missing required field."""
        schema = ActionSchema(
            type="object",
            required=["channel", "message"],
            properties={
                "channel": {"type": "string"},
                "message": {"type": "string"},
            },
        )

        errors = schema.validate_config({"channel": "#general"})
        assert len(errors) == 1
        assert "message" in errors[0]


class TestActionStatus:
    """Tests for ActionStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert ActionStatus.PENDING.value == "pending"
        assert ActionStatus.RUNNING.value == "running"
        assert ActionStatus.SUCCESS.value == "success"
        assert ActionStatus.FAILED.value == "failed"
        assert ActionStatus.SKIPPED.value == "skipped"


class TestActionCategory:
    """Tests for ActionCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert ActionCategory.DATA.value == "data"
        assert ActionCategory.INTEGRATION.value == "integration"
        assert ActionCategory.LOGIC.value == "logic"
        assert ActionCategory.NOTIFICATION.value == "notification"
        assert ActionCategory.UTILITY.value == "utility"
