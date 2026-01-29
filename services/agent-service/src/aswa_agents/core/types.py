"""Core type definitions for the agent framework."""

from enum import Enum
from typing import TypeVar


class ActionType(str, Enum):
    """Types of actions agents can perform."""

    # Document Actions
    SUMMARIZE = "summarize"
    EXTRACT_ENTITIES = "extract_entities"
    EXTRACT_ACTION_ITEMS = "extract_action_items"
    SEARCH_KNOWLEDGE_BASE = "search_knowledge_base"

    # Ticketing Actions
    CREATE_JIRA_TICKET = "create_jira_ticket"
    UPDATE_JIRA_TICKET = "update_jira_ticket"
    CREATE_ZENDESK_TICKET = "create_zendesk_ticket"
    CREATE_LINEAR_ISSUE = "create_linear_issue"

    # Communication Actions
    SEND_SLACK_MESSAGE = "send_slack_message"
    SEND_TEAMS_MESSAGE = "send_teams_message"
    SEND_EMAIL = "send_email"

    # Document Management Actions
    CREATE_DOCUMENT = "create_document"
    UPDATE_DOCUMENT = "update_document"
    UPDATE_CONFLUENCE = "update_confluence"
    UPDATE_NOTION = "update_notion"

    # Calendar Actions
    SCHEDULE_MEETING = "schedule_meeting"

    # Integration Actions
    CALL_WEBHOOK = "call_webhook"
    LOOKUP_CRM = "lookup_crm"

    # Logic Actions
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    SET_VARIABLE = "set_variable"
    TRANSFORM = "transform"
    DELAY = "delay"

    # Custom
    CUSTOM = "custom"


class ActionStatus(str, Enum):
    """Status of an action execution."""

    PENDING = "pending"
    QUEUED = "queued"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class ApprovalLevel(str, Enum):
    """Approval requirements for actions."""

    AUTO = "auto"  # Execute immediately without approval
    NOTIFY = "notify"  # Execute and notify afterwards
    REVIEW = "review"  # Require explicit approval before execution
    MANUAL = "manual"  # Never auto-execute, always require manual trigger


class TriggerType(str, Enum):
    """Types of triggers that can start an agent."""

    DOCUMENT_INGESTED = "document_ingested"
    DOCUMENT_UPDATED = "document_updated"
    EMAIL_RECEIVED = "email_received"
    SLACK_MESSAGE = "slack_message"
    TEAMS_MESSAGE = "teams_message"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    INSIGHT_DETECTED = "insight_detected"
    JIRA_ISSUE = "jira_issue"
    MANUAL = "manual"


class ConfidenceLevel(str, Enum):
    """Confidence level for agent decisions."""

    HIGH = "high"  # > 0.9
    MEDIUM = "medium"  # 0.7 - 0.9
    LOW = "low"  # 0.5 - 0.7
    VERY_LOW = "very_low"  # < 0.5


# Type variable for generic action types
T_Action = TypeVar("T_Action", bound="Action")
