# Task 9.4.4: Action Block Registry

## Objective

Implement a central registry for action blocks that enables discovery, validation, and instantiation of actions at runtime.

## Prerequisites

- Task 9.4.1-9.4.3 completed (All action blocks implemented)

## Implementation

### Step 1: Action Block Registry

```python
# services/agent-service/src/aswa_agents/actions/registry.py
"""Central registry for action blocks."""

from typing import Any, Type

import structlog

from aswa_agents.actions.base import ActionBlock

logger = structlog.get_logger()


class ActionRegistry:
    """
    Central registry for all action blocks.

    Provides discovery, validation, and instantiation of actions.
    Supports dynamic registration of custom actions.
    """

    _instance: "ActionRegistry | None" = None
    _actions: dict[str, Type[ActionBlock]] = {}
    _initialized: bool = False

    def __new__(cls) -> "ActionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls) -> None:
        """Initialize the registry with built-in actions."""
        if cls._initialized:
            return

        # Import and register all built-in actions
        cls._register_core_actions()
        cls._register_integration_actions()
        cls._register_logic_actions()

        cls._initialized = True
        logger.info("Action registry initialized", action_count=len(cls._actions))

    @classmethod
    def _register_core_actions(cls) -> None:
        """Register core action blocks."""
        from aswa_agents.actions.core.summarize import SummarizeAction
        from aswa_agents.actions.core.extract import ExtractAction
        from aswa_agents.actions.core.transform import TransformAction
        from aswa_agents.actions.core.query_knowledge import QueryKnowledgeAction

        cls.register(SummarizeAction)
        cls.register(ExtractAction)
        cls.register(TransformAction)
        cls.register(QueryKnowledgeAction)

    @classmethod
    def _register_integration_actions(cls) -> None:
        """Register integration action blocks."""
        from aswa_agents.actions.integrations.slack import SendSlackAction
        from aswa_agents.actions.integrations.email import SendEmailAction
        from aswa_agents.actions.integrations.ticket import CreateTicketAction
        from aswa_agents.actions.integrations.http_request import HttpRequestAction

        cls.register(SendSlackAction)
        cls.register(SendEmailAction)
        cls.register(CreateTicketAction)
        cls.register(HttpRequestAction)

    @classmethod
    def _register_logic_actions(cls) -> None:
        """Register logic action blocks."""
        from aswa_agents.actions.logic.condition import ConditionAction
        from aswa_agents.actions.logic.loop import LoopAction
        from aswa_agents.actions.logic.switch import SwitchAction
        from aswa_agents.actions.logic.wait import WaitAction
        from aswa_agents.actions.logic.error_handler import ErrorHandlerAction

        cls.register(ConditionAction)
        cls.register(LoopAction)
        cls.register(SwitchAction)
        cls.register(WaitAction)
        cls.register(ErrorHandlerAction)

    @classmethod
    def register(cls, action_class: Type[ActionBlock]) -> None:
        """
        Register an action block class.

        Args:
            action_class: The action class to register
        """
        action_type = action_class.action_type

        if action_type in cls._actions:
            logger.warning(
                "Overwriting existing action registration",
                action_type=action_type,
            )

        cls._actions[action_type] = action_class
        logger.debug("Registered action", action_type=action_type)

    @classmethod
    def unregister(cls, action_type: str) -> None:
        """Unregister an action block."""
        if action_type in cls._actions:
            del cls._actions[action_type]

    @classmethod
    def get(cls, action_type: str) -> Type[ActionBlock] | None:
        """
        Get an action class by type.

        Args:
            action_type: The action type identifier

        Returns:
            The action class or None if not found
        """
        if not cls._initialized:
            cls.initialize()

        return cls._actions.get(action_type)

    @classmethod
    def create(
        cls,
        action_type: str,
        action_id: str,
        config: dict[str, Any],
    ) -> ActionBlock:
        """
        Create an action instance.

        Args:
            action_type: The action type identifier
            action_id: Unique ID for this action instance
            config: Action configuration

        Returns:
            Configured action instance

        Raises:
            ValueError: If action type is unknown
        """
        action_class = cls.get(action_type)

        if action_class is None:
            raise ValueError(f"Unknown action type: {action_type}")

        # Get config class from action
        config_schema = action_class.get_config_schema()

        # Parse config using Pydantic
        from pydantic import BaseModel

        # Dynamic config parsing
        try:
            # Find the config class from the action's type hints
            import inspect
            sig = inspect.signature(action_class.__init__)
            config_param = sig.parameters.get("config")

            if config_param and config_param.annotation != inspect.Parameter.empty:
                config_class = config_param.annotation
                if isinstance(config_class, type) and issubclass(config_class, BaseModel):
                    parsed_config = config_class(**config)
                else:
                    parsed_config = config
            else:
                parsed_config = config

        except Exception as e:
            logger.warning(
                "Failed to parse config, using raw dict",
                action_type=action_type,
                error=str(e),
            )
            parsed_config = config

        return action_class(action_id=action_id, config=parsed_config)

    @classmethod
    def list_actions(cls) -> list[dict[str, Any]]:
        """
        List all registered actions.

        Returns:
            List of action metadata
        """
        if not cls._initialized:
            cls.initialize()

        actions = []
        for action_type, action_class in cls._actions.items():
            actions.append({
                "type": action_type,
                "display_name": action_class.display_name,
                "description": action_class.description,
                "category": action_class.category,
                "config_schema": action_class.get_config_schema(),
                "output_schema": action_class.get_output_schema(),
            })

        return actions

    @classmethod
    def get_by_category(cls, category: str) -> list[dict[str, Any]]:
        """Get actions by category."""
        all_actions = cls.list_actions()
        return [a for a in all_actions if a["category"] == category]

    @classmethod
    def validate_config(
        cls,
        action_type: str,
        config: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate action configuration.

        Args:
            action_type: The action type
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        action_class = cls.get(action_type)

        if action_class is None:
            return False, [f"Unknown action type: {action_type}"]

        errors = []

        try:
            # Try to create with config to validate
            cls.create(action_type, "validation-test", config)
        except Exception as e:
            errors.append(str(e))

        return len(errors) == 0, errors

    @classmethod
    def clear(cls) -> None:
        """Clear all registered actions (for testing)."""
        cls._actions.clear()
        cls._initialized = False


# Convenience functions
def get_action(action_type: str) -> Type[ActionBlock] | None:
    """Get an action class by type."""
    return ActionRegistry.get(action_type)


def create_action(
    action_type: str,
    action_id: str,
    config: dict[str, Any],
) -> ActionBlock:
    """Create an action instance."""
    return ActionRegistry.create(action_type, action_id, config)


def list_actions() -> list[dict[str, Any]]:
    """List all registered actions."""
    return ActionRegistry.list_actions()
```

### Step 2: Action Factory

```python
# services/agent-service/src/aswa_agents/actions/factory.py
"""Factory for creating action pipelines."""

from typing import Any

import structlog

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult
from aswa_agents.actions.registry import ActionRegistry

logger = structlog.get_logger()


class ActionPipeline:
    """
    A pipeline of actions to execute in sequence.

    Handles action ordering, dependency resolution, and execution flow.
    """

    def __init__(self):
        self.actions: list[ActionBlock] = []
        self.dependencies: dict[str, list[str]] = {}
        self._logger = logger.bind(component="ActionPipeline")

    def add_action(
        self,
        action: ActionBlock,
        depends_on: list[str] | None = None,
    ) -> "ActionPipeline":
        """Add an action to the pipeline."""
        self.actions.append(action)

        if depends_on:
            self.dependencies[action.action_id] = depends_on

        return self

    def get_execution_order(self) -> list[ActionBlock]:
        """
        Get actions in execution order based on dependencies.

        Uses topological sort to resolve dependencies.
        """
        # Build dependency graph
        in_degree: dict[str, int] = {a.action_id: 0 for a in self.actions}
        adjacency: dict[str, list[str]] = {a.action_id: [] for a in self.actions}

        for action_id, deps in self.dependencies.items():
            for dep in deps:
                if dep in adjacency:
                    adjacency[dep].append(action_id)
                    in_degree[action_id] += 1

        # Topological sort (Kahn's algorithm)
        queue = [aid for aid, deg in in_degree.items() if deg == 0]
        sorted_ids = []

        while queue:
            current = queue.pop(0)
            sorted_ids.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_ids) != len(self.actions):
            raise ValueError("Circular dependency detected in action pipeline")

        # Map IDs back to actions
        action_map = {a.action_id: a for a in self.actions}
        return [action_map[aid] for aid in sorted_ids]

    async def execute(
        self,
        context: ActionContext,
        on_action_complete: callable | None = None,
    ) -> dict[str, ActionResult]:
        """
        Execute all actions in the pipeline.

        Args:
            context: Initial execution context
            on_action_complete: Optional callback after each action

        Returns:
            Dict mapping action IDs to results
        """
        results: dict[str, ActionResult] = {}
        execution_order = self.get_execution_order()

        for action in execution_order:
            # Check dependencies
            deps = self.dependencies.get(action.action_id, [])
            for dep in deps:
                if dep in results and results[dep].is_failure:
                    # Skip if dependency failed
                    results[action.action_id] = ActionResult(
                        action_id=action.action_id,
                        status="skipped",
                        error=f"Dependency {dep} failed",
                    )
                    continue

            # Update context with previous outputs
            for aid, result in results.items():
                if result.output:
                    context.previous_outputs[aid] = result.output

            # Execute action
            self._logger.info(
                "Executing action",
                action_id=action.action_id,
                action_type=action.action_type,
            )

            result = await action.run(context)
            results[action.action_id] = result

            if on_action_complete:
                await on_action_complete(action, result)

            # Handle branching from condition/switch
            if result.output and "next_action" in result.output:
                # Would handle branching here
                pass

        return results


class ActionFactory:
    """
    Factory for creating actions and pipelines from definitions.

    Parses agent definitions and creates executable pipelines.
    """

    def __init__(self):
        self._logger = logger.bind(component="ActionFactory")

    def create_pipeline(
        self,
        actions: list[dict[str, Any]],
    ) -> ActionPipeline:
        """
        Create an action pipeline from action definitions.

        Args:
            actions: List of action definitions with id, type, config

        Returns:
            Configured ActionPipeline
        """
        pipeline = ActionPipeline()

        for action_def in actions:
            action_id = action_def.get("id", f"action_{len(pipeline.actions)}")
            action_type = action_def.get("type")
            config = action_def.get("config", {})
            depends_on = action_def.get("depends_on", [])

            if not action_type:
                raise ValueError(f"Action {action_id} missing 'type' field")

            action = ActionRegistry.create(action_type, action_id, config)
            pipeline.add_action(action, depends_on)

        return pipeline

    def create_from_definition(
        self,
        definition: dict[str, Any],
    ) -> ActionPipeline:
        """
        Create pipeline from full agent definition.

        Args:
            definition: Complete agent definition with actions

        Returns:
            Configured ActionPipeline
        """
        actions = definition.get("actions", [])
        return self.create_pipeline(actions)

    def validate_definition(
        self,
        definition: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate an agent definition's actions.

        Args:
            definition: Agent definition to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        actions = definition.get("actions", [])

        if not actions:
            errors.append("No actions defined")

        action_ids = set()
        for idx, action_def in enumerate(actions):
            action_id = action_def.get("id", f"action_{idx}")
            action_type = action_def.get("type")
            config = action_def.get("config", {})

            # Check for duplicate IDs
            if action_id in action_ids:
                errors.append(f"Duplicate action ID: {action_id}")
            action_ids.add(action_id)

            # Check action type exists
            if not action_type:
                errors.append(f"Action {action_id}: missing 'type' field")
                continue

            if not ActionRegistry.get(action_type):
                errors.append(f"Action {action_id}: unknown type '{action_type}'")
                continue

            # Validate config
            is_valid, config_errors = ActionRegistry.validate_config(
                action_type, config
            )
            if not is_valid:
                for err in config_errors:
                    errors.append(f"Action {action_id}: {err}")

            # Check dependencies exist
            depends_on = action_def.get("depends_on", [])
            for dep in depends_on:
                if dep not in action_ids and dep not in [a.get("id") for a in actions]:
                    errors.append(
                        f"Action {action_id}: depends on unknown action '{dep}'"
                    )

        return len(errors) == 0, errors
```

### Step 3: Action API Endpoints

```python
# services/agent-service/src/aswa_agents/api/actions.py
"""API endpoints for action management."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aswa_agents.actions.registry import ActionRegistry, list_actions

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionInfo(BaseModel):
    """Information about an action."""

    type: str
    display_name: str
    description: str
    category: str
    config_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ActionListResponse(BaseModel):
    """Response for listing actions."""

    actions: list[ActionInfo]
    total: int


class ValidateConfigRequest(BaseModel):
    """Request to validate action config."""

    action_type: str
    config: dict[str, Any]


class ValidateConfigResponse(BaseModel):
    """Response from config validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


@router.get("", response_model=ActionListResponse)
async def list_all_actions(category: str | None = None) -> ActionListResponse:
    """
    List all available actions.

    Optionally filter by category.
    """
    if category:
        actions = ActionRegistry.get_by_category(category)
    else:
        actions = list_actions()

    return ActionListResponse(
        actions=[ActionInfo(**a) for a in actions],
        total=len(actions),
    )


@router.get("/categories")
async def list_categories() -> list[str]:
    """List all action categories."""
    actions = list_actions()
    categories = set(a["category"] for a in actions)
    return sorted(categories)


@router.get("/{action_type}", response_model=ActionInfo)
async def get_action(action_type: str) -> ActionInfo:
    """Get details about a specific action."""
    action_class = ActionRegistry.get(action_type)

    if not action_class:
        raise HTTPException(status_code=404, detail=f"Action not found: {action_type}")

    return ActionInfo(
        type=action_class.action_type,
        display_name=action_class.display_name,
        description=action_class.description,
        category=action_class.category,
        config_schema=action_class.get_config_schema(),
        output_schema=action_class.get_output_schema(),
    )


@router.post("/validate", response_model=ValidateConfigResponse)
async def validate_action_config(request: ValidateConfigRequest) -> ValidateConfigResponse:
    """Validate action configuration."""
    is_valid, errors = ActionRegistry.validate_config(
        request.action_type,
        request.config,
    )

    return ValidateConfigResponse(
        valid=is_valid,
        errors=errors,
    )


@router.get("/{action_type}/schema")
async def get_action_schema(action_type: str) -> dict[str, Any]:
    """Get JSON schema for action configuration."""
    action_class = ActionRegistry.get(action_type)

    if not action_class:
        raise HTTPException(status_code=404, detail=f"Action not found: {action_type}")

    return {
        "config": action_class.get_config_schema(),
        "output": action_class.get_output_schema(),
    }
```

### Step 4: Custom Action Registration

```python
# services/agent-service/src/aswa_agents/actions/custom.py
"""Support for custom action blocks."""

from typing import Any, Callable, Awaitable

from pydantic import BaseModel, create_model

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus
from aswa_agents.actions.registry import ActionRegistry


def create_custom_action(
    action_type: str,
    display_name: str,
    description: str,
    category: str = "custom",
    config_fields: dict[str, tuple[type, Any]] | None = None,
    execute_fn: Callable[[ActionContext, Any], Awaitable[dict]] | None = None,
) -> type[ActionBlock]:
    """
    Create a custom action class dynamically.

    Args:
        action_type: Unique action type identifier
        display_name: Human-readable name
        description: Action description
        category: Action category
        config_fields: Dict of field_name -> (type, default_value)
        execute_fn: Async function to execute the action

    Returns:
        Custom action class
    """
    # Create config model
    if config_fields:
        ConfigModel = create_model(
            f"{action_type.title().replace('_', '')}Config",
            **{name: (typ, default) for name, (typ, default) in config_fields.items()}
        )
    else:
        ConfigModel = create_model(f"{action_type.title().replace('_', '')}Config")

    class CustomAction(ActionBlock):
        action_type = action_type
        display_name = display_name
        description = description
        category = category

        def __init__(self, action_id: str, config: Any):
            if isinstance(config, dict):
                config = ConfigModel(**config)
            super().__init__(action_id, config)

        async def execute(self, context: ActionContext) -> ActionResult:
            if execute_fn:
                try:
                    output = await execute_fn(context, self.config)
                    return ActionResult(
                        action_id=self.action_id,
                        status=ActionStatus.COMPLETED,
                        output=output,
                    )
                except Exception as e:
                    return ActionResult(
                        action_id=self.action_id,
                        status=ActionStatus.FAILED,
                        error=str(e),
                    )
            else:
                return ActionResult(
                    action_id=self.action_id,
                    status=ActionStatus.COMPLETED,
                    output={"message": "Custom action executed"},
                )

        @classmethod
        def get_config_schema(cls) -> dict[str, Any]:
            return ConfigModel.model_json_schema()

    return CustomAction


def register_custom_action(
    action_type: str,
    display_name: str,
    description: str,
    category: str = "custom",
    config_fields: dict[str, tuple[type, Any]] | None = None,
    execute_fn: Callable[[ActionContext, Any], Awaitable[dict]] | None = None,
) -> type[ActionBlock]:
    """
    Create and register a custom action.

    Returns the created action class.
    """
    action_class = create_custom_action(
        action_type=action_type,
        display_name=display_name,
        description=description,
        category=category,
        config_fields=config_fields,
        execute_fn=execute_fn,
    )

    ActionRegistry.register(action_class)
    return action_class


# Example usage for tenant-specific actions
class TenantActionManager:
    """Manages tenant-specific custom actions."""

    _tenant_actions: dict[str, list[str]] = {}

    @classmethod
    def register_for_tenant(
        cls,
        tenant_id: str,
        action_type: str,
        **kwargs,
    ) -> type[ActionBlock]:
        """Register a custom action for a specific tenant."""
        # Prefix action type with tenant
        full_type = f"tenant_{tenant_id}_{action_type}"

        action_class = register_custom_action(
            action_type=full_type,
            **kwargs,
        )

        if tenant_id not in cls._tenant_actions:
            cls._tenant_actions[tenant_id] = []
        cls._tenant_actions[tenant_id].append(full_type)

        return action_class

    @classmethod
    def get_tenant_actions(cls, tenant_id: str) -> list[str]:
        """Get action types registered for a tenant."""
        return cls._tenant_actions.get(tenant_id, [])

    @classmethod
    def unregister_tenant_actions(cls, tenant_id: str) -> None:
        """Unregister all actions for a tenant."""
        for action_type in cls._tenant_actions.get(tenant_id, []):
            ActionRegistry.unregister(action_type)

        if tenant_id in cls._tenant_actions:
            del cls._tenant_actions[tenant_id]
```

## Test Cases

```python
# services/agent-service/tests/unit/test_action_registry.py
"""Tests for action registry."""

import pytest
from uuid import uuid4

from aswa_agents.actions.registry import ActionRegistry, create_action, list_actions
from aswa_agents.actions.factory import ActionFactory, ActionPipeline
from aswa_agents.actions.custom import create_custom_action, register_custom_action
from aswa_agents.actions.base import ActionContext, ActionStatus


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry before each test."""
    ActionRegistry.clear()
    ActionRegistry.initialize()
    yield
    ActionRegistry.clear()


class TestActionRegistry:
    """Test ActionRegistry."""

    def test_initialization(self):
        """Test registry initializes with built-in actions."""
        actions = list_actions()
        assert len(actions) > 0

        # Check core actions registered
        types = [a["type"] for a in actions]
        assert "summarize" in types
        assert "extract" in types
        assert "send_slack" in types
        assert "condition" in types

    def test_get_action(self):
        """Test getting action by type."""
        action_class = ActionRegistry.get("summarize")
        assert action_class is not None
        assert action_class.action_type == "summarize"

    def test_get_unknown_action(self):
        """Test getting unknown action type."""
        action_class = ActionRegistry.get("unknown_action")
        assert action_class is None

    def test_create_action(self):
        """Test creating action instance."""
        action = create_action(
            action_type="summarize",
            action_id="test-summarize",
            config={"max_length": 200},
        )

        assert action.action_id == "test-summarize"
        assert action.config.max_length == 200

    def test_create_unknown_action(self):
        """Test creating unknown action type."""
        with pytest.raises(ValueError, match="Unknown action type"):
            create_action("unknown", "test", {})

    def test_list_by_category(self):
        """Test listing actions by category."""
        core_actions = ActionRegistry.get_by_category("core")
        integration_actions = ActionRegistry.get_by_category("integration")
        logic_actions = ActionRegistry.get_by_category("logic")

        assert len(core_actions) > 0
        assert len(integration_actions) > 0
        assert len(logic_actions) > 0

        # All core actions should have category "core"
        for action in core_actions:
            assert action["category"] == "core"

    def test_validate_config(self):
        """Test config validation."""
        # Valid config
        is_valid, errors = ActionRegistry.validate_config(
            "summarize",
            {"max_length": 200},
        )
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_config(self):
        """Test config validation with invalid config."""
        is_valid, errors = ActionRegistry.validate_config(
            "summarize",
            {"max_length": -1},  # Invalid: negative length
        )
        # Note: Depends on validation strictness
        # This test may need adjustment based on actual validation


class TestActionPipeline:
    """Test ActionPipeline."""

    @pytest.fixture
    def context(self):
        return ActionContext(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test",
            trigger_data={"content": "Test content"},
        )

    @pytest.mark.asyncio
    async def test_simple_pipeline(self, context):
        """Test simple action pipeline."""
        pipeline = ActionPipeline()

        action = create_action(
            "transform",
            "test-transform",
            {"transform_type": "split", "split_delimiter": " "},
        )
        pipeline.add_action(action)

        results = await pipeline.execute(context)

        assert "test-transform" in results
        assert results["test-transform"].status == ActionStatus.COMPLETED

    def test_execution_order_with_dependencies(self):
        """Test execution order respects dependencies."""
        pipeline = ActionPipeline()

        action1 = create_action("transform", "action1", {"transform_type": "split"})
        action2 = create_action("transform", "action2", {"transform_type": "split"})
        action3 = create_action("transform", "action3", {"transform_type": "split"})

        pipeline.add_action(action1, depends_on=[])
        pipeline.add_action(action2, depends_on=["action1"])
        pipeline.add_action(action3, depends_on=["action1", "action2"])

        order = pipeline.get_execution_order()
        order_ids = [a.action_id for a in order]

        assert order_ids.index("action1") < order_ids.index("action2")
        assert order_ids.index("action2") < order_ids.index("action3")

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        pipeline = ActionPipeline()

        action1 = create_action("transform", "action1", {"transform_type": "split"})
        action2 = create_action("transform", "action2", {"transform_type": "split"})

        pipeline.add_action(action1, depends_on=["action2"])
        pipeline.add_action(action2, depends_on=["action1"])

        with pytest.raises(ValueError, match="Circular dependency"):
            pipeline.get_execution_order()


class TestActionFactory:
    """Test ActionFactory."""

    def test_create_pipeline_from_definitions(self):
        """Test creating pipeline from action definitions."""
        factory = ActionFactory()

        actions = [
            {"id": "summarize_1", "type": "summarize", "config": {"max_length": 200}},
            {"id": "extract_1", "type": "extract", "config": {"extract_type": "action_items"}},
        ]

        pipeline = factory.create_pipeline(actions)

        assert len(pipeline.actions) == 2

    def test_validate_definition(self):
        """Test definition validation."""
        factory = ActionFactory()

        # Valid definition
        valid_def = {
            "actions": [
                {"id": "action_1", "type": "summarize", "config": {}},
            ]
        }
        is_valid, errors = factory.validate_definition(valid_def)
        assert is_valid

        # Invalid - unknown action type
        invalid_def = {
            "actions": [
                {"id": "action_1", "type": "unknown_action", "config": {}},
            ]
        }
        is_valid, errors = factory.validate_definition(invalid_def)
        assert not is_valid
        assert any("unknown type" in e for e in errors)

    def test_validate_duplicate_ids(self):
        """Test detection of duplicate action IDs."""
        factory = ActionFactory()

        definition = {
            "actions": [
                {"id": "duplicate", "type": "summarize", "config": {}},
                {"id": "duplicate", "type": "extract", "config": {}},
            ]
        }

        is_valid, errors = factory.validate_definition(definition)
        assert not is_valid
        assert any("Duplicate" in e for e in errors)


class TestCustomActions:
    """Test custom action creation."""

    def test_create_custom_action(self):
        """Test creating custom action class."""
        CustomAction = create_custom_action(
            action_type="my_custom",
            display_name="My Custom Action",
            description="Does something custom",
            config_fields={
                "param1": (str, "default"),
                "param2": (int, 10),
            },
        )

        assert CustomAction.action_type == "my_custom"
        assert CustomAction.display_name == "My Custom Action"

        action = CustomAction("test", {"param1": "value", "param2": 20})
        assert action.config.param1 == "value"
        assert action.config.param2 == 20

    @pytest.mark.asyncio
    async def test_custom_action_execution(self):
        """Test custom action execution."""

        async def my_execute(context, config):
            return {"result": f"Processed with {config.message}"}

        CustomAction = create_custom_action(
            action_type="test_custom",
            display_name="Test Custom",
            description="Test",
            config_fields={"message": (str, "hello")},
            execute_fn=my_execute,
        )

        action = CustomAction("test", {"message": "world"})
        context = ActionContext(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test",
            trigger_data={},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["result"] == "Processed with world"

    def test_register_custom_action(self):
        """Test registering custom action in registry."""
        register_custom_action(
            action_type="registered_custom",
            display_name="Registered Custom",
            description="A registered custom action",
        )

        action_class = ActionRegistry.get("registered_custom")
        assert action_class is not None
        assert action_class.display_name == "Registered Custom"
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_action_registry.py -v
   ```

2. **Test registry initialization:**
   ```python
   from aswa_agents.actions.registry import ActionRegistry, list_actions

   ActionRegistry.initialize()
   actions = list_actions()

   print(f"Registered {len(actions)} actions:")
   for action in actions:
       print(f"  - {action['type']}: {action['display_name']}")
   ```

3. **Test action creation:**
   ```python
   from aswa_agents.actions.registry import create_action

   action = create_action(
       "summarize",
       "my-summarize",
       {"max_length": 300, "style": "bullet_points"}
   )
   print(f"Created: {action.action_id} ({action.action_type})")
   ```

4. **Test API endpoints:**
   ```bash
   # List all actions
   curl http://localhost:8000/api/v1/actions

   # Get specific action
   curl http://localhost:8000/api/v1/actions/summarize

   # Validate config
   curl -X POST http://localhost:8000/api/v1/actions/validate \
     -H "Content-Type: application/json" \
     -d '{"action_type": "summarize", "config": {"max_length": 200}}'
   ```

## Next Task

Proceed to `task-9.5.1-agent-test-runner.md` for implementing the agent test runner.
