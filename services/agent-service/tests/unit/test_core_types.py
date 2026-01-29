"""Tests for core type definitions."""

import pytest

from aswa_agents.core.types import (
    ActionType,
    ActionStatus,
    ApprovalLevel,
    TriggerType,
    ConfidenceLevel,
)


class TestActionType:
    """Test ActionType enum."""

    def test_action_types_exist(self):
        """Test all expected action types exist."""
        assert ActionType.SUMMARIZE.value == "summarize"
        assert ActionType.CREATE_JIRA_TICKET.value == "create_jira_ticket"
        assert ActionType.SEND_SLACK_MESSAGE.value == "send_slack_message"

    def test_action_type_string_value(self):
        """Test action types are string enums."""
        assert isinstance(ActionType.SUMMARIZE.value, str)

    def test_document_actions(self):
        """Test document action types."""
        assert ActionType.EXTRACT_ENTITIES.value == "extract_entities"
        assert ActionType.EXTRACT_ACTION_ITEMS.value == "extract_action_items"
        assert ActionType.SEARCH_KNOWLEDGE_BASE.value == "search_knowledge_base"

    def test_communication_actions(self):
        """Test communication action types."""
        assert ActionType.SEND_TEAMS_MESSAGE.value == "send_teams_message"
        assert ActionType.SEND_EMAIL.value == "send_email"

    def test_logic_actions(self):
        """Test logic action types."""
        assert ActionType.CONDITION.value == "condition"
        assert ActionType.LOOP.value == "loop"
        assert ActionType.PARALLEL.value == "parallel"
        assert ActionType.SET_VARIABLE.value == "set_variable"


class TestActionStatus:
    """Test ActionStatus enum."""

    def test_terminal_states(self):
        """Test terminal status values."""
        terminal = [
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
            ActionStatus.TIMED_OUT,
        ]
        assert all(s.value for s in terminal)

    def test_pending_states(self):
        """Test pending status values."""
        pending = [
            ActionStatus.PENDING,
            ActionStatus.QUEUED,
            ActionStatus.AWAITING_APPROVAL,
        ]
        assert all(s.value for s in pending)

    def test_approval_states(self):
        """Test approval status values."""
        assert ActionStatus.APPROVED.value == "approved"
        assert ActionStatus.REJECTED.value == "rejected"

    def test_execution_states(self):
        """Test execution status values."""
        assert ActionStatus.EXECUTING.value == "executing"
        assert ActionStatus.SKIPPED.value == "skipped"


class TestApprovalLevel:
    """Test ApprovalLevel enum."""

    def test_approval_ordering(self):
        """Test approval levels exist."""
        levels = [
            ApprovalLevel.AUTO,
            ApprovalLevel.NOTIFY,
            ApprovalLevel.REVIEW,
            ApprovalLevel.MANUAL,
        ]
        assert len(levels) == 4

    def test_approval_values(self):
        """Test approval level values."""
        assert ApprovalLevel.AUTO.value == "auto"
        assert ApprovalLevel.NOTIFY.value == "notify"
        assert ApprovalLevel.REVIEW.value == "review"
        assert ApprovalLevel.MANUAL.value == "manual"


class TestTriggerType:
    """Test TriggerType enum."""

    def test_trigger_types_exist(self):
        """Test all expected trigger types exist."""
        assert TriggerType.DOCUMENT_INGESTED.value == "document_ingested"
        assert TriggerType.EMAIL_RECEIVED.value == "email_received"
        assert TriggerType.SCHEDULED.value == "scheduled"
        assert TriggerType.WEBHOOK.value == "webhook"
        assert TriggerType.MANUAL.value == "manual"

    def test_message_triggers(self):
        """Test message trigger types."""
        assert TriggerType.SLACK_MESSAGE.value == "slack_message"
        assert TriggerType.TEAMS_MESSAGE.value == "teams_message"


class TestConfidenceLevel:
    """Test ConfidenceLevel enum."""

    def test_confidence_levels(self):
        """Test confidence level values."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.VERY_LOW.value == "very_low"
