"""Agent definition generation models."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TriggerDefinition(BaseModel):
    """Generated trigger configuration."""

    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ConditionDefinition(BaseModel):
    """Generated condition configuration."""

    id: str = Field(default_factory=lambda: f"condition_{uuid4().hex[:8]}")
    type: str  # "expression", "match", "contains"
    expression: str
    description: str = ""


class ActionDefinition(BaseModel):
    """Generated action configuration."""

    id: str = Field(default_factory=lambda: f"action_{uuid4().hex[:8]}")
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    description: str = ""


class VariableDefinition(BaseModel):
    """Variable definition for the agent."""

    name: str
    source: str  # "trigger", "action_result", "config"
    path: str  # JSON path or expression
    default: Any = None


class ApprovalDefinition(BaseModel):
    """Approval configuration for the agent."""

    mode: str = "review"  # auto, notify, review, manual
    timeout_hours: int = 24
    reviewers: list[str] = Field(default_factory=list)
    confidence_threshold: float = 0.9


class ErrorHandlingDefinition(BaseModel):
    """Error handling configuration."""

    on_failure: str = "stop"  # stop, continue, retry
    max_retries: int = 3
    retry_delay_seconds: int = 5
    notification_channel: str | None = None


class RateLimitDefinition(BaseModel):
    """Rate limiting configuration."""

    max_executions_per_hour: int = 100
    max_executions_per_day: int = 1000


class GeneratedAgentDefinition(BaseModel):
    """Complete generated agent definition."""

    # Metadata
    name: str
    display_name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)

    # Components
    trigger: TriggerDefinition
    conditions: list[ConditionDefinition] = Field(default_factory=list)
    variables: list[VariableDefinition] = Field(default_factory=list)
    actions: list[ActionDefinition] = Field(default_factory=list)

    # Configuration
    approval: ApprovalDefinition = Field(default_factory=ApprovalDefinition)
    error_handling: ErrorHandlingDefinition = Field(default_factory=ErrorHandlingDefinition)
    rate_limit: RateLimitDefinition | None = None

    # Generation metadata
    generation_confidence: float = 0.0
    generation_notes: list[str] = Field(default_factory=list)

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        import yaml
        return yaml.dump(
            self.model_dump(exclude={"generation_confidence", "generation_notes"}),
            default_flow_style=False,
            sort_keys=False,
        )
