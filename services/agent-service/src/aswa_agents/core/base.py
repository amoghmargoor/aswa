"""Base class for all ASWA AI Agents."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import structlog

from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
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

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return self.config.get(key, default)

    def __repr__(self) -> str:
        return f"{self.name}(version={self.version})"
