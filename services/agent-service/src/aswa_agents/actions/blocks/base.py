"""Base classes for action blocks."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class ActionCategory(str, Enum):
    """Categories of actions."""

    DATA = "data"
    INTEGRATION = "integration"
    LOGIC = "logic"
    NOTIFICATION = "notification"
    UTILITY = "utility"


class ActionStatus(str, Enum):
    """Execution status of an action."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionContext(BaseModel):
    """Context passed to action execution."""

    agent_id: UUID
    run_id: UUID
    tenant_id: UUID
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    previous_outputs: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable from context."""
        return self.variables.get(name, default)

    def get_previous_output(self, action_id: str) -> Any:
        """Get output from a previous action."""
        return self.previous_outputs.get(action_id)

    def get_secret(self, name: str) -> str | None:
        """Get a secret value."""
        return self.secrets.get(name)


class ActionResult(BaseModel):
    """Result of action execution."""

    action_id: str
    status: ActionStatus
    output: Any = None
    error: str | None = None
    duration_ms: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionSchema(BaseModel):
    """Schema for action configuration."""

    type: str
    required: list[str] = Field(default_factory=list)
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate config against schema."""
        errors = []
        for field in self.required:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        return errors


class ActionBlock(ABC):
    """Base class for all action blocks."""

    # Class-level metadata (to be overridden by subclasses)
    action_type: ClassVar[str] = "base"
    category: ClassVar[ActionCategory] = ActionCategory.UTILITY
    display_name: ClassVar[str] = "Base Action"
    description: ClassVar[str] = "Base action block"
    icon: ClassVar[str] = "zap"
    schema: ClassVar[ActionSchema] = ActionSchema(type="object")

    def __init__(self, action_id: str, config: dict[str, Any]):
        self.action_id = action_id
        self.config = config
        self._logger = logger.bind(
            action_type=self.action_type,
            action_id=action_id,
        )

    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action."""
        pass

    async def validate(self) -> list[str]:
        """Validate action configuration."""
        return self.schema.validate_config(self.config)

    def get_required_secrets(self) -> list[str]:
        """Get list of secrets required by this action."""
        return []

    def get_required_connectors(self) -> list[str]:
        """Get list of connectors required by this action."""
        return []

    def _create_result(
        self,
        status: ActionStatus,
        output: Any = None,
        error: str | None = None,
        duration_ms: float = 0,
        **metadata: Any,
    ) -> ActionResult:
        """Helper to create action result."""
        return ActionResult(
            action_id=self.action_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            metadata=metadata,
        )


class CompositeAction(ActionBlock):
    """Action that contains child actions."""

    action_type: ClassVar[str] = "composite"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC

    def __init__(self, action_id: str, config: dict[str, Any], children: list[ActionBlock]):
        super().__init__(action_id, config)
        self.children = children

    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute composite action with children."""
        pass
