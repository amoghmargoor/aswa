"""Tests for core data models."""

import pytest
from uuid import uuid4

from aswa_agents.core.models import (
    Entity,
    Insight,
    TriggerData,
    ActionContext,
    Action,
    ActionResult,
)
from aswa_agents.core.types import (
    ActionType,
    ActionStatus,
    ConfidenceLevel,
    TriggerType,
)


class TestEntity:
    """Test Entity model."""

    def test_create_entity(self):
        """Test entity creation."""
        entity = Entity(
            type="PERSON",
            name="John Doe",
            value="john@example.com",
            confidence=0.95,
        )
        assert entity.type == "PERSON"
        assert entity.name == "John Doe"
        assert entity.confidence == 0.95

    def test_entity_defaults(self):
        """Test entity default values."""
        entity = Entity(type="ORG", name="Acme Inc")
        assert entity.value is None
        assert entity.confidence == 1.0
        assert entity.metadata == {}


class TestInsight:
    """Test Insight model."""

    def test_create_insight(self):
        """Test insight creation."""
        insight = Insight(
            tenant_id="tenant-1",
            type="BUG_REPORT",
            title="Login Bug",
            summary="Users cannot login",
            confidence=0.87,
        )
        assert insight.tenant_id == "tenant-1"
        assert insight.type == "BUG_REPORT"
        assert insight.id is not None

    def test_confidence_level_high(self):
        """Test high confidence level."""
        insight = Insight(
            tenant_id="t",
            type="t",
            title="t",
            summary="s",
            confidence=0.95,
        )
        assert insight.get_confidence_level() == ConfidenceLevel.HIGH

    def test_confidence_level_medium(self):
        """Test medium confidence level."""
        insight = Insight(
            tenant_id="t",
            type="t",
            title="t",
            summary="s",
            confidence=0.75,
        )
        assert insight.get_confidence_level() == ConfidenceLevel.MEDIUM

    def test_confidence_level_low(self):
        """Test low confidence level."""
        insight = Insight(
            tenant_id="t",
            type="t",
            title="t",
            summary="s",
            confidence=0.55,
        )
        assert insight.get_confidence_level() == ConfidenceLevel.LOW

    def test_confidence_level_very_low(self):
        """Test very low confidence level."""
        insight = Insight(
            tenant_id="t",
            type="t",
            title="t",
            summary="s",
            confidence=0.3,
        )
        assert insight.get_confidence_level() == ConfidenceLevel.VERY_LOW


class TestTriggerData:
    """Test TriggerData model."""

    def test_create_trigger_data(self):
        """Test trigger data creation."""
        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        assert trigger.trigger_type == TriggerType.MANUAL
        assert trigger.trigger_id is not None
        assert trigger.timestamp is not None

    def test_trigger_with_payload(self):
        """Test trigger with payload."""
        trigger = TriggerData(
            trigger_type=TriggerType.WEBHOOK,
            source="external-api",
            payload={"event": "new_issue"},
        )
        assert trigger.source == "external-api"
        assert trigger.payload["event"] == "new_issue"


class TestActionContext:
    """Test ActionContext model."""

    def test_create_context(self):
        """Test context creation."""
        context = ActionContext(
            agent_id=uuid4(),
            agent_name="TestAgent",
            tenant_id="tenant-1",
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
        )
        assert context.tenant_id == "tenant-1"
        assert context.dry_run is False

    def test_variable_management(self):
        """Test variable get/set."""
        context = ActionContext(
            agent_id=uuid4(),
            agent_name="TestAgent",
            tenant_id="tenant-1",
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
        )

        context.set_variable("foo", "bar")
        assert context.get_variable("foo") == "bar"
        assert context.get_variable("missing", "default") == "default"

    def test_connector_tokens(self):
        """Test connector token management."""
        context = ActionContext(
            agent_id=uuid4(),
            agent_name="TestAgent",
            tenant_id="tenant-1",
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            connector_tokens={"jira": "token123"},
        )

        assert context.get_connector_token("jira") == "token123"
        assert context.get_connector_token("slack") is None


class TestAction:
    """Test Action model."""

    def test_create_action(self):
        """Test action creation."""
        action = Action(
            type=ActionType.CREATE_JIRA_TICKET,
            target_system="jira",
            parameters={"project": "TEST"},
            confidence=0.9,
        )
        assert action.type == ActionType.CREATE_JIRA_TICKET
        assert action.confidence == 0.9

    def test_action_defaults(self):
        """Test action default values."""
        action = Action(
            type=ActionType.SUMMARIZE,
            target_system="aswa",
        )
        assert action.confidence == 1.0
        assert action.rollback_possible is True
        assert action.max_retries == 3
        assert action.parameters == {}

    def test_action_confidence_levels(self):
        """Test action confidence level method."""
        action = Action(type=ActionType.CUSTOM, target_system="test", confidence=0.95)
        assert action.get_confidence_level() == ConfidenceLevel.HIGH

        action.confidence = 0.75
        assert action.get_confidence_level() == ConfidenceLevel.MEDIUM

    def test_action_with_dependencies(self):
        """Test action with dependencies."""
        dep_id = uuid4()
        action = Action(
            type=ActionType.SEND_EMAIL,
            target_system="email",
            depends_on=[dep_id],
        )
        assert dep_id in action.depends_on


class TestActionResult:
    """Test ActionResult model."""

    def test_create_result(self):
        """Test result creation."""
        result = ActionResult(
            action_id=uuid4(),
            status=ActionStatus.PENDING,
        )
        assert result.status == ActionStatus.PENDING
        assert result.started_at is not None

    def test_mark_completed(self):
        """Test marking result as completed."""
        result = ActionResult(
            action_id=uuid4(),
            status=ActionStatus.EXECUTING,
        )
        result.mark_completed({"ticket_id": "TEST-123"})

        assert result.status == ActionStatus.COMPLETED
        assert result.is_success
        assert result.result_data["ticket_id"] == "TEST-123"
        assert result.completed_at is not None

    def test_mark_failed(self):
        """Test marking result as failed."""
        result = ActionResult(
            action_id=uuid4(),
            status=ActionStatus.EXECUTING,
        )
        result.mark_failed("Connection timeout", error_code="TIMEOUT")

        assert result.status == ActionStatus.FAILED
        assert result.is_failure
        assert result.error_message == "Connection timeout"
        assert result.error_code == "TIMEOUT"

    def test_is_failure_states(self):
        """Test is_failure property for different states."""
        result = ActionResult(action_id=uuid4(), status=ActionStatus.TIMED_OUT)
        assert result.is_failure

        result.status = ActionStatus.CANCELLED
        assert result.is_failure

        result.status = ActionStatus.COMPLETED
        assert not result.is_failure
