"""Models for NLP agent generation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class IntentType(str, Enum):
    """Types of user intents for agent creation."""

    # Trigger intents
    TRIGGER_ON_EMAIL = "trigger_on_email"
    TRIGGER_ON_SLACK = "trigger_on_slack"
    TRIGGER_ON_DOCUMENT = "trigger_on_document"
    TRIGGER_ON_SCHEDULE = "trigger_on_schedule"
    TRIGGER_ON_WEBHOOK = "trigger_on_webhook"
    TRIGGER_ON_INSIGHT = "trigger_on_insight"

    # Action intents
    ACTION_SUMMARIZE = "action_summarize"
    ACTION_EXTRACT = "action_extract"
    ACTION_SEARCH = "action_search"
    ACTION_CREATE_TICKET = "action_create_ticket"
    ACTION_SEND_MESSAGE = "action_send_message"
    ACTION_SEND_EMAIL = "action_send_email"
    ACTION_UPDATE_DOCUMENT = "action_update_document"
    ACTION_CALL_WEBHOOK = "action_call_webhook"

    # Condition intents
    CONDITION_FILTER = "condition_filter"
    CONDITION_MATCH = "condition_match"

    # Other
    UNKNOWN = "unknown"


class ExtractedEntity(BaseModel):
    """An entity extracted from the user's description."""

    type: str  # email_address, channel_name, project_key, etc.
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    span: tuple[int, int] | None = None  # Character positions in original text


class ExtractedIntent(BaseModel):
    """A single intent extracted from user input."""

    id: UUID = Field(default_factory=uuid4)
    type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    description: str  # Human-readable description
    parameters: dict[str, Any] = Field(default_factory=dict)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    source_text: str = ""  # The part of input this was extracted from


class IntentExtractionResult(BaseModel):
    """Result of intent extraction from user input."""

    id: UUID = Field(default_factory=uuid4)
    original_input: str
    normalized_input: str
    trigger_intents: list[ExtractedIntent] = Field(default_factory=list)
    action_intents: list[ExtractedIntent] = Field(default_factory=list)
    condition_intents: list[ExtractedIntent] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    raw_llm_response: dict[str, Any] | None = None
    processing_time_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def all_intents(self) -> list[ExtractedIntent]:
        """Get all intents."""
        return self.trigger_intents + self.action_intents + self.condition_intents

    @property
    def has_trigger(self) -> bool:
        """Check if a trigger was identified."""
        return len(self.trigger_intents) > 0

    @property
    def has_actions(self) -> bool:
        """Check if actions were identified."""
        return len(self.action_intents) > 0


class ConversationMessage(BaseModel):
    """A message in the agent creation conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=utcnow)
    intents: IntentExtractionResult | None = None


class AgentCreationSession(BaseModel):
    """Tracks a multi-turn agent creation conversation."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    user_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    accumulated_intents: IntentExtractionResult | None = None
    status: str = "in_progress"  # in_progress, completed, cancelled
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
