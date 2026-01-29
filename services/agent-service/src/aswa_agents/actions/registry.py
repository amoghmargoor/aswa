"""Action block registry for managing action blocks."""

from typing import Dict, Type


class ActionBlockRegistry:
    """Registry for managing action block classes."""

    _blocks: Dict[str, Type] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize the action block registry."""
        cls._initialized = True
        cls._blocks = {}

    @classmethod
    def register(cls, block_id: str, block_class: Type) -> None:
        """Register an action block class."""
        cls._blocks[block_id] = block_class

    @classmethod
    def get(cls, block_id: str) -> Type | None:
        """Get an action block class by ID."""
        return cls._blocks.get(block_id)

    @classmethod
    def list_blocks(cls, category: str | None = None) -> list[str]:
        """List all registered block IDs, optionally filtered by category."""
        return list(cls._blocks.keys())

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if registry is initialized."""
        return cls._initialized
