"""Action block registry."""

from typing import Type

import structlog

from aswa_agents.actions.blocks.base import ActionBlock, ActionCategory, ActionSchema

logger = structlog.get_logger()


class ActionRegistry:
    """Registry for action blocks."""

    _actions: dict[str, Type[ActionBlock]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, action_class: Type[ActionBlock]) -> Type[ActionBlock]:
        """Register an action class."""
        action_type = action_class.action_type
        if action_type in cls._actions:
            logger.warning(
                "Action already registered, overwriting",
                action_type=action_type,
            )
        cls._actions[action_type] = action_class
        logger.debug("Action registered", action_type=action_type)
        return action_class

    @classmethod
    def get(cls, action_type: str) -> Type[ActionBlock] | None:
        """Get action class by type."""
        cls._ensure_initialized()
        return cls._actions.get(action_type)

    @classmethod
    def create(cls, action_type: str, action_id: str, config: dict) -> ActionBlock:
        """Create action instance by type."""
        action_class = cls.get(action_type)
        if not action_class:
            raise ValueError(f"Unknown action type: {action_type}")
        return action_class(action_id, config)

    @classmethod
    def get_all(cls) -> dict[str, Type[ActionBlock]]:
        """Get all registered actions."""
        cls._ensure_initialized()
        return dict(cls._actions)

    @classmethod
    def get_by_category(cls, category: ActionCategory) -> list[Type[ActionBlock]]:
        """Get all actions in a category."""
        cls._ensure_initialized()
        return [
            action for action in cls._actions.values()
            if action.category == category
        ]

    @classmethod
    def get_schema(cls, action_type: str) -> ActionSchema | None:
        """Get schema for action type."""
        action_class = cls.get(action_type)
        if action_class:
            return action_class.schema
        return None

    @classmethod
    def get_action_info(cls, action_type: str) -> dict | None:
        """Get action info for documentation/UI."""
        action_class = cls.get(action_type)
        if not action_class:
            return None

        return {
            "type": action_class.action_type,
            "category": action_class.category.value,
            "display_name": action_class.display_name,
            "description": action_class.description,
            "icon": action_class.icon,
            "schema": action_class.schema.model_dump(),
        }

    @classmethod
    def get_all_action_info(cls) -> list[dict]:
        """Get info for all registered actions."""
        cls._ensure_initialized()
        return [
            cls.get_action_info(action_type)
            for action_type in cls._actions
        ]

    @classmethod
    def get_catalog(cls) -> dict[str, list[dict]]:
        """Get action catalog grouped by category."""
        cls._ensure_initialized()
        catalog: dict[str, list[dict]] = {}

        for category in ActionCategory:
            actions = cls.get_by_category(category)
            if actions:
                catalog[category.value] = [
                    cls.get_action_info(action.action_type)
                    for action in actions
                ]

        return catalog

    @classmethod
    def clear(cls) -> None:
        """Clear all registered actions."""
        cls._actions.clear()
        cls._initialized = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize with built-in actions."""
        if cls._initialized:
            return

        # Import and register all built-in actions
        from aswa_agents.actions.blocks.data_actions import (
            SummarizeAction,
            ExtractAction,
            TransformAction,
            AggregateAction,
        )
        from aswa_agents.actions.blocks.integration_actions import (
            SendSlackAction,
            SendEmailAction,
            CreateTicketAction,
            WebhookAction,
        )
        from aswa_agents.actions.blocks.logic_actions import (
            FilterAction,
            BranchAction,
            LoopAction,
            DelayAction,
            RetryAction,
        )

        # Data actions
        cls.register(SummarizeAction)
        cls.register(ExtractAction)
        cls.register(TransformAction)
        cls.register(AggregateAction)

        # Integration actions
        cls.register(SendSlackAction)
        cls.register(SendEmailAction)
        cls.register(CreateTicketAction)
        cls.register(WebhookAction)

        # Logic actions
        cls.register(FilterAction)
        cls.register(BranchAction)
        cls.register(LoopAction)
        cls.register(DelayAction)
        cls.register(RetryAction)

        cls._initialized = True
        logger.info("Action registry initialized", action_count=len(cls._actions))

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure registry is initialized."""
        if not cls._initialized:
            cls.initialize()


# Decorator for registering custom actions
def register_action(cls: Type[ActionBlock]) -> Type[ActionBlock]:
    """Decorator to register an action class."""
    return ActionRegistry.register(cls)
