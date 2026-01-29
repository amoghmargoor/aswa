"""Data models for agents, actions, and execution context."""

from datetime import datetime, timezone
from typing import Any
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
        self.completed_at = datetime.now(timezone.utc)
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
        self.completed_at = datetime.now(timezone.utc)
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
