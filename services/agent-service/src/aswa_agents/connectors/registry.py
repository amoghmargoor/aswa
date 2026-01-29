"""Connector registry for external service connections."""

from typing import Dict, Type


class ConnectorRegistry:
    """Registry for managing external service connectors."""

    _instance: "ConnectorRegistry | None" = None
    _connectors: Dict[str, Type] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize the connector registry."""
        cls._initialized = True
        cls._connectors = {}

    @classmethod
    def register(cls, name: str, connector_class: Type) -> None:
        """Register a connector class."""
        cls._connectors[name] = connector_class

    @classmethod
    def get(cls, name: str) -> Type | None:
        """Get a connector class by name."""
        return cls._connectors.get(name)

    @classmethod
    def list_connectors(cls) -> list[str]:
        """List all registered connector names."""
        return list(cls._connectors.keys())
