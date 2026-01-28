from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class Citation:
    """A citation to a source."""
    index: int
    document_id: UUID | None
    document_name: str
    page_number: int | None = None
    excerpt: str = ""
    relevance_score: float = 0.0

    def format(self) -> str:
        ref = f"[{self.index}]"
        if self.page_number:
            return f"{ref} {self.document_name}, p.{self.page_number}"
        return f"{ref} {self.document_name}"


@dataclass
class GeneratedAnswer:
    """A generated answer with citations."""
    id: UUID = field(default_factory=uuid4)
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    query: str = ""
    reasoning: str | None = None
    generation_time_ms: int = 0
    token_count: int = 0
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_citations(self) -> bool:
        return len(self.citations) > 0

    def format_with_citations(self) -> str:
        """Format answer with citation references."""
        result = self.answer
        if self.citations:
            result += "\n\nSources:\n"
            for citation in self.citations:
                result += f"  {citation.format()}\n"
        return result


@dataclass
class ValidationResult:
    """Result of answer validation."""
    is_valid: bool
    confidence: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
