"""Clarification dialog models and logic."""

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ClarificationType(str, Enum):
    """Types of clarification needed."""

    MISSING_TRIGGER = "missing_trigger"
    MISSING_ACTION = "missing_action"
    AMBIGUOUS_TARGET = "ambiguous_target"
    MISSING_PARAMETER = "missing_parameter"
    MULTIPLE_OPTIONS = "multiple_options"
    CONFIRMATION = "confirmation"


class ClarificationOption(BaseModel):
    """An option presented to the user for clarification."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    label: str
    description: str = ""
    value: Any = None
    is_recommended: bool = False


class ClarificationQuestion(BaseModel):
    """A structured clarification question."""

    id: UUID = Field(default_factory=uuid4)
    type: ClarificationType
    question: str
    context: str = ""  # Why we're asking
    options: list[ClarificationOption] = Field(default_factory=list)
    allows_custom_input: bool = True
    related_intent_id: str | None = None
    parameter_name: str | None = None
    priority: int = 0  # Higher = more important


class ClarificationResponse(BaseModel):
    """User's response to a clarification question."""

    question_id: UUID
    selected_option_id: str | None = None
    custom_input: str | None = None


class ClarificationState(BaseModel):
    """State of the clarification process."""

    pending_questions: list[ClarificationQuestion] = Field(default_factory=list)
    answered_questions: list[tuple[ClarificationQuestion, ClarificationResponse]] = Field(default_factory=list)
    is_complete: bool = False
    completion_confidence: float = 0.0
