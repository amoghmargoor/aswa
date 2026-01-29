"""Base class for action blocks."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from aswa_agents.core.models import ActionContext, ActionResult
from aswa_agents.core.types import ActionStatus, ActionType

logger = structlog.get_logger()


class ActionBlockConfig(BaseModel):
    """Configuration schema for action blocks."""

    model_config = {"extra": "allow"}  # Allow additional fields


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
        action_id: UUID | str | None = None,
    ) -> ActionResult:
        """Convert block output to ActionResult."""
        if action_id is None:
            action_id = uuid4()
        elif isinstance(action_id, str):
            action_id = UUID(action_id)

        return ActionResult(
            action_id=action_id,
            status=ActionStatus.COMPLETED if output.success else ActionStatus.FAILED,
            result_data=output.data if output.success else None,
            error_message=output.error,
            completed_at=datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return f"ActionBlock({self.id}: {self.name})"
