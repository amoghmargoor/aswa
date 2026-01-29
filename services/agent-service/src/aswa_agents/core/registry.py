"""Agent registry for managing registered agents."""

from typing import Dict, Type


class AgentRegistry:
    """Registry for managing agent classes."""

    _agents: Dict[str, Type] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize the agent registry."""
        cls._initialized = True
        cls._agents = {}

    @classmethod
    def register(cls, name: str, agent_class: Type) -> None:
        """Register an agent class."""
        cls._agents[name] = agent_class

    @classmethod
    def get(cls, name: str) -> Type | None:
        """Get an agent class by name."""
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> list[str]:
        """List all registered agent names."""
        return list(cls._agents.keys())

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if registry is initialized."""
        return cls._initialized
