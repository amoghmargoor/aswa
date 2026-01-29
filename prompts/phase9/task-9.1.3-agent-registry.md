# Task 9.1.3: Agent Registry

## Objective

Implement a singleton registry for discovering and managing agents. The registry enables dynamic agent registration, discovery by trigger type, and tenant-specific agent configuration.

## Prerequisites

- Task 9.1.1 completed (Agent Service setup)
- Task 9.1.2 completed (Agent base classes)

## Implementation

### Step 1: Agent Registry Implementation

```python
# services/agent-service/src/aswa_agents/core/registry.py
"""Agent registry for discovering and managing agents."""

from typing import Type, TypeVar
import structlog

from aswa_agents.core.base import Agent
from aswa_agents.core.models import TriggerData

logger = structlog.get_logger()

T = TypeVar("T", bound=Agent)


class AgentRegistry:
    """
    Singleton registry for managing available agents.

    The registry provides:
    1. Registration of agent classes via decorator
    2. Discovery of agents by trigger type
    3. Tenant-specific agent configuration and filtering
    4. Lazy instantiation of agent instances

    Usage:
        # Register an agent
        @AgentRegistry.register
        class MyAgent(Agent):
            ...

        # Find agents for a trigger
        agents = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
    """

    _instance: "AgentRegistry | None" = None
    _agents: dict[str, Type[Agent]] = {}
    _initialized: bool = False

    def __new__(cls) -> "AgentRegistry":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls) -> None:
        """Initialize the registry and discover built-in agents."""
        if cls._initialized:
            return

        logger.info("Initializing agent registry")

        # Import built-in agents to trigger registration
        cls._discover_builtin_agents()

        cls._initialized = True
        logger.info(
            "Agent registry initialized",
            agent_count=len(cls._agents),
            agents=list(cls._agents.keys()),
        )

    @classmethod
    def _discover_builtin_agents(cls) -> None:
        """Import built-in agents to trigger registration."""
        try:
            # Import built-in agent modules
            from aswa_agents.agents import builtin  # noqa: F401
        except ImportError as e:
            logger.warning("Could not import built-in agents", error=str(e))

    @classmethod
    def register(cls, agent_class: Type[T]) -> Type[T]:
        """
        Decorator to register an agent class.

        Usage:
            @AgentRegistry.register
            class MyAgent(Agent):
                ...
        """
        name = agent_class.__name__

        if name in cls._agents:
            logger.warning(
                "Agent already registered, overwriting",
                agent_name=name,
            )

        cls._agents[name] = agent_class
        logger.debug("Registered agent", agent_name=name)

        return agent_class

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister an agent by name.

        Returns True if agent was found and removed.
        """
        if name in cls._agents:
            del cls._agents[name]
            logger.debug("Unregistered agent", agent_name=name)
            return True
        return False

    @classmethod
    def get_agent_class(cls, name: str) -> Type[Agent] | None:
        """Get agent class by name."""
        return cls._agents.get(name)

    @classmethod
    def get_agent(cls, name: str, config: dict | None = None) -> Agent | None:
        """
        Get an instantiated agent by name.

        Args:
            name: Agent class name
            config: Optional agent configuration

        Returns:
            Instantiated agent or None if not found
        """
        agent_class = cls.get_agent_class(name)
        if agent_class:
            return agent_class(config or {})
        return None

    @classmethod
    def get_all_agents(cls) -> dict[str, Type[Agent]]:
        """Get all registered agent classes."""
        return cls._agents.copy()

    @classmethod
    def list_agents(cls) -> list[dict]:
        """
        List all registered agents with metadata.

        Returns:
            List of agent metadata dictionaries
        """
        agents = []
        for name, agent_class in cls._agents.items():
            instance = agent_class({})
            agents.append({
                "name": name,
                "version": instance.version,
                "description": instance.description,
                "supported_trigger_types": instance.supported_trigger_types,
                "required_permissions": instance.required_permissions,
                "required_connectors": instance.required_connectors,
            })
        return agents

    @classmethod
    def find_agents_for_trigger(
        cls,
        trigger: TriggerData,
        tenant_config: dict,
    ) -> list[tuple[Type[Agent], dict]]:
        """
        Find all agents that can handle the given trigger.

        Args:
            trigger: The trigger event data
            tenant_config: Tenant configuration including enabled agents

        Returns:
            List of (agent_class, agent_config) tuples
        """
        matching = []

        # Get list of enabled agents for tenant
        enabled_agents = tenant_config.get("enabled_agents")
        if enabled_agents is None:
            # If not specified, all agents are enabled
            enabled_agents = list(cls._agents.keys())

        # Get disabled agents
        disabled_agents = tenant_config.get("disabled_agents", [])

        for name, agent_class in cls._agents.items():
            # Check if agent is enabled for tenant
            if name not in enabled_agents:
                continue

            # Check if agent is explicitly disabled
            if name in disabled_agents:
                continue

            # Get agent-specific config
            agent_config = tenant_config.get(f"agent_{name}", {})

            # Check if agent is disabled in its own config
            if not agent_config.get("enabled", True):
                continue

            # Create temporary instance to check trigger type support
            instance = agent_class(agent_config)

            # Check if this agent supports the trigger type
            if trigger.trigger_type.value in instance.supported_trigger_types:
                matching.append((agent_class, agent_config))
                logger.debug(
                    "Found matching agent",
                    agent_name=name,
                    trigger_type=trigger.trigger_type.value,
                )

        return matching

    @classmethod
    def find_agents_by_permission(cls, permission: str) -> list[Type[Agent]]:
        """
        Find all agents that require a specific permission.

        Args:
            permission: Permission string (e.g., "jira:write")

        Returns:
            List of agent classes requiring that permission
        """
        matching = []
        for agent_class in cls._agents.values():
            instance = agent_class({})
            if permission in instance.required_permissions:
                matching.append(agent_class)
        return matching

    @classmethod
    def find_agents_by_connector(cls, connector_id: str) -> list[Type[Agent]]:
        """
        Find all agents that require a specific connector.

        Args:
            connector_id: Connector ID (e.g., "jira", "slack")

        Returns:
            List of agent classes requiring that connector
        """
        matching = []
        for agent_class in cls._agents.values():
            instance = agent_class({})
            if connector_id in instance.required_connectors:
                matching.append(agent_class)
        return matching

    @classmethod
    def validate_agent_config(
        cls,
        name: str,
        config: dict,
    ) -> tuple[bool, list[str]]:
        """
        Validate agent configuration.

        Args:
            name: Agent name
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        agent_class = cls.get_agent_class(name)
        if not agent_class:
            return False, [f"Unknown agent: {name}"]

        errors = []

        # Check required config fields
        instance = agent_class(config)
        required_fields = getattr(instance, "required_config_fields", [])
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required config field: {field}")

        return len(errors) == 0, errors

    @classmethod
    def clear(cls) -> None:
        """Clear all registered agents. Useful for testing."""
        cls._agents.clear()
        cls._initialized = False
        logger.debug("Agent registry cleared")

    @classmethod
    def count(cls) -> int:
        """Get number of registered agents."""
        return len(cls._agents)
```

### Step 2: Agent Metadata Model

```python
# services/agent-service/src/aswa_agents/core/metadata.py
"""Agent metadata models for serialization."""

from typing import Any
from pydantic import BaseModel, Field


class AgentMetadata(BaseModel):
    """Metadata about a registered agent."""

    name: str
    version: str
    description: str
    supported_trigger_types: list[str]
    required_permissions: list[str]
    required_connectors: list[str]
    config_schema: dict[str, Any] = Field(default_factory=dict)
    category: str = "general"
    icon: str = "bot"
    is_builtin: bool = True


class AgentListResponse(BaseModel):
    """Response for listing agents."""

    agents: list[AgentMetadata]
    total: int
```

### Step 3: Registry API Endpoints

```python
# services/agent-service/src/aswa_agents/api/endpoints/registry.py
"""API endpoints for agent registry."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aswa_agents.api.dependencies import get_current_tenant
from aswa_agents.core.registry import AgentRegistry
from aswa_agents.core.metadata import AgentMetadata, AgentListResponse


router = APIRouter()


@router.get("/registry", response_model=AgentListResponse)
async def list_registered_agents(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    category: str | None = Query(None, description="Filter by category"),
    connector: str | None = Query(None, description="Filter by required connector"),
) -> AgentListResponse:
    """List all registered agents available for the tenant."""
    agents = []

    for agent_info in AgentRegistry.list_agents():
        # Apply filters
        if connector and connector not in agent_info.get("required_connectors", []):
            continue

        # Get category from agent class
        agent_class = AgentRegistry.get_agent_class(agent_info["name"])
        agent_category = getattr(agent_class, "category", "general") if agent_class else "general"

        if category and agent_category != category:
            continue

        agents.append(AgentMetadata(
            name=agent_info["name"],
            version=agent_info["version"],
            description=agent_info["description"],
            supported_trigger_types=agent_info["supported_trigger_types"],
            required_permissions=agent_info["required_permissions"],
            required_connectors=agent_info["required_connectors"],
            category=agent_category,
        ))

    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/registry/{agent_name}", response_model=AgentMetadata)
async def get_agent_info(
    agent_name: str,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> AgentMetadata:
    """Get detailed information about a specific agent."""
    from fastapi import HTTPException

    agent_class = AgentRegistry.get_agent_class(agent_name)
    if not agent_class:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    instance = agent_class({})

    return AgentMetadata(
        name=agent_name,
        version=instance.version,
        description=instance.description,
        supported_trigger_types=instance.supported_trigger_types,
        required_permissions=instance.required_permissions,
        required_connectors=instance.required_connectors,
        category=getattr(instance, "category", "general"),
    )


@router.get("/registry/by-trigger/{trigger_type}")
async def list_agents_by_trigger(
    trigger_type: str,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> list[str]:
    """List agents that support a specific trigger type."""
    agents = []
    for agent_info in AgentRegistry.list_agents():
        if trigger_type in agent_info["supported_trigger_types"]:
            agents.append(agent_info["name"])
    return agents
```

### Step 4: Update Routes

```python
# Update services/agent-service/src/aswa_agents/api/routes.py

from fastapi import APIRouter

from aswa_agents.api.endpoints import (
    agents,
    executions,
    approvals,
    templates,
    actions,
    generation,
    registry,  # Add this
)


router = APIRouter()

# Include all endpoint routers
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(registry.router, tags=["registry"])  # Add this
router.include_router(executions.router, prefix="/executions", tags=["executions"])
router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(actions.router, prefix="/actions", tags=["actions"])
router.include_router(generation.router, prefix="/generate", tags=["generation"])
```

## Test Cases

```python
# services/agent-service/tests/unit/test_registry.py
"""Tests for agent registry."""

import pytest
from aswa_agents.core.registry import AgentRegistry
from aswa_agents.core.base import Agent
from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    TriggerData,
)
from aswa_agents.core.types import ActionType, ActionStatus, TriggerType
from uuid import uuid4


class TestAction(Action):
    """Test action."""
    pass


@AgentRegistry.register
class TestAgent(Agent[TestAction]):
    """Test agent for registry tests."""

    category = "test"

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["manual", "webhook"]

    @property
    def required_permissions(self) -> list[str]:
        return ["test:read", "test:write"]

    async def should_trigger(self, trigger: TriggerData, context: ActionContext) -> bool:
        return True

    async def plan_actions(self, trigger: TriggerData, context: ActionContext) -> list[TestAction]:
        return []

    async def execute(self, action: TestAction, context: ActionContext) -> ActionResult:
        return ActionResult(action_id=action.id, status=ActionStatus.COMPLETED)


@AgentRegistry.register
class AnotherTestAgent(Agent[TestAction]):
    """Another test agent."""

    @property
    def supported_trigger_types(self) -> list[str]:
        return ["email_received"]

    @property
    def required_permissions(self) -> list[str]:
        return ["email:read"]

    async def should_trigger(self, trigger: TriggerData, context: ActionContext) -> bool:
        return True

    async def plan_actions(self, trigger: TriggerData, context: ActionContext) -> list[TestAction]:
        return []

    async def execute(self, action: TestAction, context: ActionContext) -> ActionResult:
        return ActionResult(action_id=action.id, status=ActionStatus.COMPLETED)


class TestAgentRegistry:
    """Test AgentRegistry class."""

    def test_register_decorator(self):
        """Test agent registration via decorator."""
        assert "TestAgent" in AgentRegistry.get_all_agents()
        assert "AnotherTestAgent" in AgentRegistry.get_all_agents()

    def test_get_agent_class(self):
        """Test getting agent class by name."""
        agent_class = AgentRegistry.get_agent_class("TestAgent")
        assert agent_class is not None
        assert agent_class.__name__ == "TestAgent"

    def test_get_agent_class_not_found(self):
        """Test getting non-existent agent."""
        agent_class = AgentRegistry.get_agent_class("NonExistent")
        assert agent_class is None

    def test_get_agent_instance(self):
        """Test getting instantiated agent."""
        agent = AgentRegistry.get_agent("TestAgent", {"key": "value"})
        assert agent is not None
        assert agent.name == "TestAgent"
        assert agent.config.get("key") == "value"

    def test_list_agents(self):
        """Test listing all agents with metadata."""
        agents = AgentRegistry.list_agents()
        assert len(agents) >= 2

        test_agent = next(a for a in agents if a["name"] == "TestAgent")
        assert test_agent["version"] == "1.0.0"
        assert "manual" in test_agent["supported_trigger_types"]
        assert "test:write" in test_agent["required_permissions"]

    def test_find_agents_for_trigger_manual(self):
        """Test finding agents for manual trigger."""
        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {}

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        agent_names = [cls.__name__ for cls, _ in matching]

        assert "TestAgent" in agent_names
        assert "AnotherTestAgent" not in agent_names

    def test_find_agents_for_trigger_email(self):
        """Test finding agents for email trigger."""
        trigger = TriggerData(trigger_type=TriggerType.EMAIL_RECEIVED)
        tenant_config = {}

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        agent_names = [cls.__name__ for cls, _ in matching]

        assert "TestAgent" not in agent_names
        assert "AnotherTestAgent" in agent_names

    def test_find_agents_respects_enabled_list(self):
        """Test that enabled_agents config is respected."""
        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"enabled_agents": ["AnotherTestAgent"]}

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        assert len(matching) == 0  # TestAgent supports manual but not enabled

    def test_find_agents_respects_disabled_list(self):
        """Test that disabled_agents config is respected."""
        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {"disabled_agents": ["TestAgent"]}

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        agent_names = [cls.__name__ for cls, _ in matching]
        assert "TestAgent" not in agent_names

    def test_find_agents_with_agent_config(self):
        """Test that agent-specific config is passed."""
        trigger = TriggerData(trigger_type=TriggerType.MANUAL)
        tenant_config = {
            "agent_TestAgent": {"custom_setting": "value"}
        }

        matching = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)
        test_agent_entry = next(
            (cls, cfg) for cls, cfg in matching if cls.__name__ == "TestAgent"
        )
        assert test_agent_entry[1].get("custom_setting") == "value"

    def test_find_agents_by_permission(self):
        """Test finding agents by permission."""
        matching = AgentRegistry.find_agents_by_permission("test:write")
        assert any(cls.__name__ == "TestAgent" for cls in matching)

    def test_find_agents_by_connector(self):
        """Test finding agents by connector."""
        matching = AgentRegistry.find_agents_by_connector("test")
        assert any(cls.__name__ == "TestAgent" for cls in matching)

    def test_validate_agent_config_unknown_agent(self):
        """Test validating config for unknown agent."""
        is_valid, errors = AgentRegistry.validate_agent_config("Unknown", {})
        assert not is_valid
        assert "Unknown agent" in errors[0]

    def test_count(self):
        """Test agent count."""
        count = AgentRegistry.count()
        assert count >= 2
```

```python
# services/agent-service/tests/integration/test_registry_api.py
"""Integration tests for registry API."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestRegistryAPI:
    """Test registry API endpoints."""

    async def test_list_registered_agents(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test listing registered agents."""
        response = await async_client.get(
            "/api/v1/registry",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert data["total"] >= 0

    async def test_get_agent_info(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting specific agent info."""
        # First list to get an agent name
        list_response = await async_client.get(
            "/api/v1/registry",
            headers=auth_headers,
        )

        if list_response.json()["total"] > 0:
            agent_name = list_response.json()["agents"][0]["name"]

            response = await async_client.get(
                f"/api/v1/registry/{agent_name}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == agent_name

    async def test_get_agent_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting non-existent agent."""
        response = await async_client.get(
            "/api/v1/registry/NonExistentAgent",
            headers=auth_headers,
        )

        assert response.status_code == 404
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/test_registry.py -v
   ```

2. **Run integration tests:**
   ```bash
   pytest tests/integration/test_registry_api.py -v
   ```

3. **Verify registry initialization:**
   ```python
   from aswa_agents.core.registry import AgentRegistry
   AgentRegistry.initialize()
   print(f"Registered agents: {AgentRegistry.count()}")
   print(AgentRegistry.list_agents())
   ```

## Next Task

Proceed to `task-9.1.4-agent-orchestrator.md` to implement the execution orchestrator.
