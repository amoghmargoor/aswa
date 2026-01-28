from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class PromptTemplate(ABC):
    """Base class for extraction prompt templates."""

    # Template name for logging/metrics
    name: str

    # The response model for instructor
    response_model: Type[BaseModel]

    # Maximum tokens for this extraction type
    max_tokens: int = 4096

    # Temperature for extraction (0 = deterministic)
    temperature: float = 0.0

    @abstractmethod
    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Get the system prompt for this extraction type."""
        ...

    @abstractmethod
    def get_user_prompt(self, text: str, context: dict[str, Any] | None = None) -> str:
        """Get the user prompt with the text to analyze."""
        ...

    def get_messages(self, text: str, context: dict[str, Any] | None = None) -> list[dict]:
        """Build the messages list for the LLM."""
        return [
            {"role": "system", "content": self.get_system_prompt(context)},
            {"role": "user", "content": self.get_user_prompt(text, context)},
        ]

    def truncate_text(self, text: str, max_chars: int = 100000) -> str:
        """Truncate text if too long, preserving structure."""
        if len(text) <= max_chars:
            return text

        # Truncate with indicator
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:
            truncated = truncated[:last_period + 1]

        return truncated + "\n\n[Text truncated due to length...]"


class PromptManager:
    """Manager for accessing and using prompt templates."""

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        self._templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        """Get a template by name."""
        if name not in self._templates:
            raise ValueError(f"Unknown prompt template: {name}")
        return self._templates[name]

    def list_templates(self) -> list[str]:
        """List all registered templates."""
        return list(self._templates.keys())


# Global prompt manager instance
prompt_manager = PromptManager()
