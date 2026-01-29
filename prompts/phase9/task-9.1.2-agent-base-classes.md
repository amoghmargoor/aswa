# Task 9.1.2: Agent Base Classes

## Objective

Define the foundational abstractions for agents, actions, and execution context. These base classes establish the contract that all agents must implement and ensure consistency across built-in and user-created agents.

## Prerequisites

- Task 9.1.1 completed (Agent Service setup)

## Design Principles

1. **Extensibility**: Easy to add new agent types without modifying core code
2. **Type Safety**: Full typing with Pydantic models for serialization
3. **Async-First**: All execution methods are async for non-blocking I/O
4. **Connector Agnostic**: Actions reference connectors by ID, not implementation
5. **Testability**: Dependency injection for all external services

## Implementation

### Step 1: Core Enums and Types

```python
# services/agent-service/src/aswa_agents/core/types.py
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
```

### Step 2: Data Models

```python
# services/agent-service/src/aswa_agents/core/models.py
"""Data models for agents, actions, and execution context."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from aswa_agents.core.types import (
    ActionStatus,
    ActionType,
    ApprovalLevel,
    ConfidenceLevel,
    TriggerType,
)


class Entity(BaseModel):
    """Represents an extracted entity."""

    type: str
    name: str
    value: Any | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Insight(BaseModel):
    """Represents an insight from document analysis."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    type: str
    title: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_documents: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)

    def get_confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence >= 0.9:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.7:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.5:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW


class TriggerData(BaseModel):
    """Data from a trigger event."""

    trigger_type: TriggerType
    trigger_id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    insight: Insight | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ActionContext(BaseModel):
    """Context for action execution."""

    execution_id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    agent_name: str
    tenant_id: str
    user_id: str | None = None
    trigger_data: TriggerData
    organization_settings: dict[str, Any] = Field(default_factory=dict)
    agent_config: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    connector_tokens: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable from context."""
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in context."""
        self.variables[name] = value

    def get_connector_token(self, connector_id: str) -> str | None:
        """Get OAuth token for a connector."""
        return self.connector_tokens.get(connector_id)


class Action(BaseModel):
    """Represents a planned action."""

    id: UUID = Field(default_factory=uuid4)
    type: ActionType
    target_system: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""
    requires_approval: ApprovalLevel = ApprovalLevel.REVIEW
    estimated_impact: str = ""
    rollback_possible: bool = True
    depends_on: list[UUID] = Field(default_factory=list)
    timeout_seconds: int = 60
    retry_count: int = 0
    max_retries: int = 3

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: Any) -> dict:
        """Ensure parameters is a dict."""
        if v is None:
            return {}
        return v

    def get_confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence >= 0.9:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.7:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.5:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW


class ActionResult(BaseModel):
    """Result of action execution."""

    action_id: UUID
    status: ActionStatus
    result_data: dict[str, Any] | None = None
    error_message: str | None = None
    error_code: str | None = None
    error_details: dict[str, Any] | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    execution_time_ms: int | None = None
    external_id: str | None = None  # ID in target system (e.g., JIRA-123)
    external_url: str | None = None  # URL to external resource
    retries_used: int = 0

    @property
    def is_success(self) -> bool:
        """Check if action completed successfully."""
        return self.status == ActionStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if action failed."""
        return self.status in (
            ActionStatus.FAILED,
            ActionStatus.TIMED_OUT,
            ActionStatus.CANCELLED,
        )

    def mark_completed(self, result_data: dict | None = None) -> None:
        """Mark action as completed."""
        self.status = ActionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result_data = result_data
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.execution_time_ms = int(delta.total_seconds() * 1000)

    def mark_failed(
        self,
        error_message: str,
        error_code: str | None = None,
        error_details: dict | None = None,
    ) -> None:
        """Mark action as failed."""
        self.status = ActionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.error_code = error_code
        self.error_details = error_details
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.execution_time_ms = int(delta.total_seconds() * 1000)


class ExecutionResult(BaseModel):
    """Result of a complete agent execution."""

    execution_id: UUID
    agent_id: UUID
    tenant_id: str
    status: ActionStatus
    trigger_data: TriggerData
    action_results: list[ActionResult] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: int | None = None
    error_message: str | None = None
    dry_run: bool = False

    @property
    def is_success(self) -> bool:
        """Check if all actions completed successfully."""
        return self.status == ActionStatus.COMPLETED and all(
            ar.is_success for ar in self.action_results
        )

    @property
    def failed_actions(self) -> list[ActionResult]:
        """Get list of failed actions."""
        return [ar for ar in self.action_results if ar.is_failure]
```

### Step 3: Base Agent Class

```python
# services/agent-service/src/aswa_agents/core/base.py
"""Base class for all ASWA AI Agents."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import structlog

from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    ActionStatus,
    TriggerData,
)
from aswa_agents.core.types import ApprovalLevel

logger = structlog.get_logger()

T = TypeVar("T", bound=Action)


class Agent(ABC, Generic[T]):
    """
    Base class for all ASWA AI Agents.

    Agents are responsible for:
    1. Determining if they should act on a trigger (should_trigger)
    2. Planning what actions to take (plan_actions)
    3. Executing approved actions (execute)

    Subclasses must implement:
    - supported_trigger_types: List of trigger types this agent handles
    - required_permissions: List of permissions needed
    - should_trigger: Logic to determine if agent should act
    - plan_actions: Logic to plan actions (often LLM-powered)
    - execute: Logic to execute a single action

    Example:
        @AgentRegistry.register
        class JiraCreatorAgent(Agent[JiraTicketAction]):
            @property
            def supported_trigger_types(self) -> list[str]:
                return ["insight_detected", "manual"]

            async def should_trigger(self, trigger: TriggerData, context: ActionContext) -> bool:
                return trigger.insight and trigger.insight.type in ["BUG_REPORT", "FEATURE_REQUEST"]

            async def plan_actions(self, trigger: TriggerData, context: ActionContext) -> list[JiraTicketAction]:
                # Use LLM to generate ticket details
                ...

            async def execute(self, action: JiraTicketAction, context: ActionContext) -> ActionResult:
                # Call Jira API
                ...
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize agent with configuration.

        Args:
            config: Agent-specific configuration from tenant settings
        """
        self.config = config or {}
        self._logger = logger.bind(agent_name=self.name)

    @property
    def name(self) -> str:
        """Return agent class name."""
        return self.__class__.__name__

    @property
    def version(self) -> str:
        """Return agent version."""
        return getattr(self.__class__, "__version__", "1.0.0")

    @property
    def description(self) -> str:
        """Return agent description."""
        return self.__class__.__doc__ or ""

    @property
    @abstractmethod
    def supported_trigger_types(self) -> list[str]:
        """
        Return list of trigger types this agent handles.

        Examples: ["insight_detected", "email_received", "manual"]
        """
        pass

    @property
    @abstractmethod
    def required_permissions(self) -> list[str]:
        """
        Return list of permissions required by this agent.

        Format: "<connector>:<permission>"
        Examples: ["jira:write", "slack:post", "aswa:search"]
        """
        pass

    @property
    def required_connectors(self) -> list[str]:
        """
        Return list of connectors this agent requires.

        Derived from required_permissions.
        """
        connectors = set()
        for perm in self.required_permissions:
            if ":" in perm:
                connectors.add(perm.split(":")[0])
        return list(connectors)

    @abstractmethod
    async def should_trigger(
        self, trigger: TriggerData, context: ActionContext
    ) -> bool:
        """
        Determine if this agent should act on the given trigger.

        Args:
            trigger: The trigger event data
            context: Execution context with tenant settings

        Returns:
            True if the agent should process this trigger
        """
        pass

    @abstractmethod
    async def plan_actions(
        self, trigger: TriggerData, context: ActionContext
    ) -> list[T]:
        """
        Plan the actions to take for the given trigger.

        This is typically the LLM-powered step that determines what
        actions to take. Actions are not executed yet - they go through
        the approval workflow first.

        Args:
            trigger: The trigger event data
            context: Execution context with variables and settings

        Returns:
            List of planned actions to execute
        """
        pass

    @abstractmethod
    async def execute(self, action: T, context: ActionContext) -> ActionResult:
        """
        Execute a single approved action.

        Should be idempotent where possible.

        Args:
            action: The action to execute
            context: Execution context

        Returns:
            Result of the action execution
        """
        pass

    async def validate_action(self, action: T, context: ActionContext) -> bool:
        """
        Validate an action before execution.

        Override to add custom validation logic.

        Args:
            action: The action to validate
            context: Execution context

        Returns:
            True if action is valid
        """
        return True

    async def pre_execute(self, action: T, context: ActionContext) -> None:
        """
        Hook called before action execution.

        Override to add pre-execution logic (e.g., logging, metrics).
        """
        self._logger.info(
            "Executing action",
            action_id=str(action.id),
            action_type=action.type.value,
            dry_run=context.dry_run,
        )

    async def post_execute(
        self, action: T, result: ActionResult, context: ActionContext
    ) -> None:
        """
        Hook called after action execution (success or failure).

        Override to add post-execution logic.
        """
        self._logger.info(
            "Action completed",
            action_id=str(action.id),
            status=result.status.value,
            duration_ms=result.execution_time_ms,
        )

    async def on_success(
        self, action: T, result: ActionResult, context: ActionContext
    ) -> None:
        """
        Hook called after successful execution.

        Override to add success handling (e.g., notifications).
        """
        pass

    async def on_failure(
        self, action: T, result: ActionResult, context: ActionContext
    ) -> None:
        """
        Hook called after failed execution.

        Override to add failure handling (e.g., alerts).
        """
        self._logger.error(
            "Action failed",
            action_id=str(action.id),
            error=result.error_message,
        )

    def get_approval_level(self, action: T, context: ActionContext) -> ApprovalLevel:
        """
        Determine approval level for an action.

        Default implementation uses confidence thresholds from org settings.
        Override for custom approval logic.

        Args:
            action: The action to check
            context: Execution context with org settings

        Returns:
            Required approval level
        """
        # Check if dry run (always show what would happen)
        if context.dry_run:
            return ApprovalLevel.MANUAL

        # Get thresholds from organization settings
        thresholds = context.organization_settings.get(
            "approval_thresholds",
            {
                "auto": 0.95,
                "notify": 0.85,
                "review": 0.7,
            },
        )

        # Check if action type is marked as high-risk
        high_risk_actions = context.organization_settings.get(
            "high_risk_actions",
            ["send_email", "create_ticket", "update_document", "call_webhook"],
        )
        if action.type.value in high_risk_actions:
            # High-risk actions require at least REVIEW
            if action.confidence >= thresholds.get("notify", 0.85):
                return ApprovalLevel.NOTIFY
            return ApprovalLevel.REVIEW

        # Standard confidence-based approval
        if action.confidence >= thresholds.get("auto", 0.95):
            return ApprovalLevel.AUTO
        elif action.confidence >= thresholds.get("notify", 0.85):
            return ApprovalLevel.NOTIFY
        elif action.confidence >= thresholds.get("review", 0.7):
            return ApprovalLevel.REVIEW
        else:
            return ApprovalLevel.MANUAL

    def get_config(self, key: str, default: any = None) -> any:
        """Get configuration value with default."""
        return self.config.get(key, default)

    def __repr__(self) -> str:
        return f"{self.name}(version={self.version})"
```

### Step 4: Action Block Base Class

```python
# services/agent-service/src/aswa_agents/actions/base.py
"""Base class for action blocks."""

from abc import ABC, abstractmethod
from typing import Any

import structlog
from pydantic import BaseModel

from aswa_agents.core.models import ActionContext, ActionResult
from aswa_agents.core.types import ActionStatus, ActionType

logger = structlog.get_logger()


class ActionBlockConfig(BaseModel):
    """Configuration schema for action blocks."""

    class Config:
        extra = "allow"  # Allow additional fields


class ActionBlockOutput(BaseModel):
    """Output from action block execution."""

    success: bool
    data: dict[str, Any] = {}
    error: str | None = None


class ActionBlock(ABC):
    """
    Base class for action blocks.

    Action blocks are the building blocks of agent workflows.
    Each block performs a specific action (summarize, create ticket, etc.)
    and can be composed into complex workflows.

    Action blocks must be:
    1. Stateless - all state passed via context
    2. Idempotent - safe to retry
    3. Observable - emit metrics and logs

    Example:
        @ActionBlockRegistry.register
        class SummarizeBlock(ActionBlock):
            id = "summarize"
            name = "Summarize Content"
            category = "ai"

            async def execute(self, config, context):
                text = config.get("text") or context.get_variable("input_text")
                summary = await self.llm.summarize(text)
                return ActionBlockOutput(success=True, data={"summary": summary})
    """

    # Block metadata - must be set by subclasses
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"  # ai, integration, logic, notification
    icon: str = "box"
    action_type: ActionType = ActionType.CUSTOM

    # Configuration schema
    config_schema: dict[str, Any] = {}

    # Connector requirements
    required_connectors: list[str] = []

    def __init__(self):
        """Initialize action block."""
        self._logger = logger.bind(block_id=self.id, block_name=self.name)

    @abstractmethod
    async def execute(
        self, config: dict[str, Any], context: ActionContext
    ) -> ActionBlockOutput:
        """
        Execute the action block.

        Args:
            config: Block configuration from agent definition
            context: Execution context with variables and tokens

        Returns:
            ActionBlockOutput with success status and data
        """
        pass

    async def validate_config(self, config: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate block configuration.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default: accept any config
        return True, None

    async def get_preview(
        self, config: dict[str, Any], context: ActionContext
    ) -> dict[str, Any]:
        """
        Get a preview of what this block would do.

        Used for dry-run and UI previews.

        Args:
            config: Block configuration
            context: Execution context

        Returns:
            Preview data describing what would happen
        """
        return {
            "block": self.id,
            "action": self.name,
            "config_summary": str(config)[:200],
        }

    def to_action_result(
        self,
        output: ActionBlockOutput,
        action_id: str | None = None,
    ) -> ActionResult:
        """Convert block output to ActionResult."""
        from uuid import uuid4
        from datetime import datetime

        return ActionResult(
            action_id=uuid4() if not action_id else action_id,
            status=ActionStatus.COMPLETED if output.success else ActionStatus.FAILED,
            result_data=output.data if output.success else None,
            error_message=output.error,
            completed_at=datetime.utcnow(),
        )

    def __repr__(self) -> str:
        return f"ActionBlock({self.id}: {self.name})"
```

### Step 5: Connector Base Class

```python
# services/agent-service/src/aswa_agents/connectors/base.py
"""Base class for external system connectors."""

from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class ConnectorConfig(BaseModel):
    """Base configuration for connectors."""

    enabled: bool = True
    timeout_seconds: int = 30
    max_retries: int = 3


class ConnectorCredentials(BaseModel):
    """Credentials for connector authentication."""

    access_token: str | None = None
    refresh_token: str | None = None
    api_key: str | None = None
    expires_at: int | None = None
    metadata: dict[str, Any] = {}


class Connector(ABC):
    """
    Base class for external system connectors.

    Connectors provide a consistent interface for interacting with
    external systems (Jira, Slack, Zendesk, etc.). They handle:
    1. Authentication (OAuth, API keys)
    2. Rate limiting
    3. Error handling
    4. Retries

    New connectors are added by:
    1. Subclassing Connector
    2. Implementing required methods
    3. Registering with ConnectorRegistry

    Example:
        @ConnectorRegistry.register
        class JiraConnector(Connector):
            id = "jira"
            name = "Jira"

            async def create_issue(self, project, issue_type, summary, ...):
                response = await self._request("POST", "/rest/api/3/issue", data={...})
                return response.json()
    """

    # Connector metadata
    id: str = ""
    name: str = ""
    description: str = ""
    icon: str = "link"
    category: str = "integration"

    # OAuth configuration
    oauth_enabled: bool = False
    oauth_scopes: list[str] = []

    # API configuration
    base_url: str = ""

    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize connector."""
        self.config = config or ConnectorConfig()
        self._credentials: ConnectorCredentials | None = None
        self._client: httpx.AsyncClient | None = None
        self._logger = logger.bind(connector_id=self.id)

    def set_credentials(self, credentials: ConnectorCredentials) -> None:
        """Set connector credentials."""
        self._credentials = credentials

    @property
    def is_authenticated(self) -> bool:
        """Check if connector has valid credentials."""
        return self._credentials is not None and (
            self._credentials.access_token is not None
            or self._credentials.api_key is not None
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with authentication."""
        if self._client is None:
            headers = {}
            if self._credentials:
                if self._credentials.access_token:
                    headers["Authorization"] = f"Bearer {self._credentials.access_token}"
                elif self._credentials.api_key:
                    headers["Authorization"] = f"Api-Key {self._credentials.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Make authenticated HTTP request."""
        client = await self._get_client()

        self._logger.debug(
            "Making request",
            method=method,
            path=path,
        )

        response = await client.request(
            method=method,
            url=path,
            json=data,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connector can connect to the external system.

        Returns:
            True if connection is successful
        """
        pass

    async def close(self) -> None:
        """Close connector and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def __repr__(self) -> str:
        return f"Connector({self.id}: {self.name})"
```

## Test Cases

```python
# services/agent-service/tests/unit/test_core_types.py
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
```

```python
# services/agent-service/tests/unit/test_core_models.py
"""Tests for core data models."""

import pytest
from datetime import datetime
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


class TestActionResult:
    """Test ActionResult model."""

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
```

```python
# services/agent-service/tests/unit/test_agent_base.py
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

    def test_required_connectors(self, agent):
        """Test required connectors extraction."""
        connectors = agent.required_connectors
        assert "jira" in connectors
        assert "slack" in connectors

    async def test_should_trigger(self, agent, context):
        """Test should_trigger logic."""
        assert await agent.should_trigger(context.trigger_data, context)

        context.trigger_data.trigger_type = TriggerType.EMAIL_RECEIVED
        assert not await agent.should_trigger(context.trigger_data, context)

    async def test_plan_actions(self, agent, context):
        """Test action planning."""
        actions = await agent.plan_actions(context.trigger_data, context)
        assert len(actions) == 1
        assert actions[0].type == ActionType.CUSTOM

    async def test_execute(self, agent, context):
        """Test action execution."""
        actions = await agent.plan_actions(context.trigger_data, context)
        result = await agent.execute(actions[0], context)
        assert result.is_success
        assert result.result_data["test"] is True

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
```

## Verification Steps

1. **Create all files:**
   ```bash
   # Create the files as specified above
   touch services/agent-service/src/aswa_agents/core/types.py
   touch services/agent-service/src/aswa_agents/core/models.py
   touch services/agent-service/src/aswa_agents/core/base.py
   touch services/agent-service/src/aswa_agents/actions/base.py
   touch services/agent-service/src/aswa_agents/connectors/base.py
   ```

2. **Run type checking:**
   ```bash
   cd services/agent-service
   mypy src/aswa_agents/core/
   ```

3. **Run unit tests:**
   ```bash
   pytest tests/unit/test_core_*.py -v
   ```

4. **Verify imports work:**
   ```bash
   python -c "from aswa_agents.core.base import Agent; print('OK')"
   python -c "from aswa_agents.core.models import Action, ActionContext; print('OK')"
   ```

## Next Task

Proceed to `task-9.1.3-agent-registry.md` to implement the agent registry.
