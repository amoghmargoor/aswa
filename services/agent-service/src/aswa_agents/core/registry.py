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

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if registry is initialized."""
        return cls._initialized
