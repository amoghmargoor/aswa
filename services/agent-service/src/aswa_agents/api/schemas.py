"""Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent status values."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ApprovalMode(str, Enum):
    """Approval mode for agent actions."""
    AUTO = "auto"
    NOTIFY = "notify"
    REVIEW = "review"
    MANUAL = "manual"


class ExecutionStatus(str, Enum):
    """Execution status values."""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Agent Schemas
class TriggerConfig(BaseModel):
    """Trigger configuration."""
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ActionConfig(BaseModel):
    """Action configuration."""
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class ApprovalConfig(BaseModel):
    """Approval configuration."""
    mode: ApprovalMode = ApprovalMode.REVIEW
    timeout_hours: int = 24
    reviewers: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    """Complete agent definition."""
    trigger: TriggerConfig
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    variables: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[ActionConfig]
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    error_handling: dict[str, Any] = Field(default_factory=dict)
    rate_limit: dict[str, Any] | None = None


class AgentCreate(BaseModel):
    """Request to create an agent."""
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    definition: AgentDefinition
    tags: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Request to update an agent."""
    display_name: str | None = None
    description: str | None = None
    definition: AgentDefinition | None = None
    status: AgentStatus | None = None
    tags: list[str] | None = None


class AgentResponse(BaseModel):
    """Agent response model."""
    id: UUID
    tenant_id: str
    name: str
    display_name: str
    description: str | None
    definition: AgentDefinition
    status: AgentStatus
    tags: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_execution_at: datetime | None
    execution_count: int
    success_count: int
    failure_count: int

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Paginated list of agents."""
    agents: list[AgentResponse]
    total: int
    limit: int
    offset: int


# Execution Schemas
class TriggerRequest(BaseModel):
    """Request to trigger an agent."""
    input_data: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class ActionResult(BaseModel):
    """Result of a single action."""
    action_id: str
    action_type: str
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int
    started_at: datetime
    completed_at: datetime | None


class ExecutionResponse(BaseModel):
    """Execution response model."""
    id: UUID
    agent_id: UUID
    tenant_id: str
    status: ExecutionStatus
    trigger_data: dict[str, Any]
    action_results: list[ActionResult]
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    error: str | None = None
    dry_run: bool = False

    model_config = {"from_attributes": True}
