# Task 9.2.1: Intent Extraction from NLP

## Objective

Implement the NLP intent extraction system that parses natural language descriptions of agents into structured intents. This is the first step in allowing users to create agents by describing what they want in plain English.

## Prerequisites

- Task 9.1.x completed (Core Agent Framework)
- LLM client configured (Anthropic/OpenAI)

## Design Principles

1. **Multi-turn Capable**: Support iterative refinement of intents
2. **Confidence Scoring**: Provide confidence levels for extracted intents
3. **Ambiguity Detection**: Identify when clarification is needed
4. **Extensible**: Easy to add new intent types

## Implementation

### Step 1: Intent Models

```python
# services/agent-service/src/aswa_agents/generation/models.py
"""Models for NLP agent generation."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intents: IntentExtractionResult | None = None


class AgentCreationSession(BaseModel):
    """Tracks a multi-turn agent creation conversation."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    user_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    accumulated_intents: IntentExtractionResult | None = None
    status: str = "in_progress"  # in_progress, completed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Step 2: Intent Extraction Prompts

```python
# services/agent-service/src/aswa_agents/generation/prompts.py
"""Prompts for NLP agent generation."""

INTENT_EXTRACTION_SYSTEM_PROMPT = """You are an AI agent creation assistant. Your job is to extract structured intents from natural language descriptions of automation workflows.

When a user describes what they want an agent to do, extract:
1. TRIGGERS: What event should start the agent (email received, Slack message, schedule, etc.)
2. ACTIONS: What the agent should do (summarize, create ticket, send message, etc.)
3. CONDITIONS: Any filters or conditions on when to act

For each intent, provide:
- type: The specific intent type
- confidence: How confident you are (0.0-1.0)
- parameters: Any specific values mentioned (email addresses, channel names, etc.)
- entities: Specific values extracted from the text
- requires_clarification: Whether you need more information
- clarification_questions: What to ask if clarification is needed

Available trigger types:
- trigger_on_email: Trigger when email is received
- trigger_on_slack: Trigger on Slack message
- trigger_on_document: Trigger when document is uploaded/updated
- trigger_on_schedule: Trigger on a schedule (daily, weekly, etc.)
- trigger_on_webhook: Trigger on webhook call
- trigger_on_insight: Trigger when an insight is detected

Available action types:
- action_summarize: Summarize content
- action_extract: Extract specific information (entities, action items, etc.)
- action_search: Search the knowledge base
- action_create_ticket: Create a Jira/Linear/Zendesk ticket
- action_send_message: Send Slack/Teams message
- action_send_email: Send an email
- action_update_document: Update a document (Confluence, Notion)
- action_call_webhook: Call an external webhook

Be conservative with confidence scores. If something is ambiguous, mark it as requiring clarification.
"""

INTENT_EXTRACTION_USER_TEMPLATE = """Extract intents from this agent description:

"{user_input}"

Respond with a JSON object in this exact format:
{{
  "normalized_input": "A cleaned up version of the user's request",
  "trigger_intents": [
    {{
      "type": "trigger_on_email",
      "confidence": 0.9,
      "description": "Trigger when support email is received",
      "parameters": {{"inbox": "support@example.com"}},
      "entities": [{{"type": "email_address", "value": "support@example.com", "confidence": 0.95}}],
      "requires_clarification": false,
      "clarification_questions": [],
      "source_text": "when we get a support email"
    }}
  ],
  "action_intents": [...],
  "condition_intents": [...],
  "overall_confidence": 0.85,
  "needs_clarification": false,
  "clarification_questions": []
}}

Only include intents that are clearly expressed. Do not invent intents that aren't mentioned."""

CLARIFICATION_PROMPT_TEMPLATE = """Based on the user's description:
"{original_input}"

We extracted these intents but need clarification:
{intents_summary}

The following questions need answers:
{questions}

Generate a friendly message asking the user for clarification. Be concise and specific.
"""

REFINEMENT_PROMPT_TEMPLATE = """The user is refining their agent description.

Original description: "{original_input}"
Previous intents extracted: {previous_intents}

User's clarification/update: "{new_input}"

Update the intents based on this new information. Return the complete updated intent structure.
"""
```

### Step 3: Intent Extractor Service

```python
# services/agent-service/src/aswa_agents/generation/intent_extractor.py
"""Intent extraction service using LLM."""

import json
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from aswa_agents.config import get_settings
from aswa_agents.generation.models import (
    ExtractedEntity,
    ExtractedIntent,
    IntentExtractionResult,
    IntentType,
)
from aswa_agents.generation.prompts import (
    INTENT_EXTRACTION_SYSTEM_PROMPT,
    INTENT_EXTRACTION_USER_TEMPLATE,
    REFINEMENT_PROMPT_TEMPLATE,
)
from aswa_agents.utils.metrics import NLP_GENERATIONS_TOTAL, NLP_GENERATION_DURATION

logger = structlog.get_logger()


class IntentExtractionError(Exception):
    """Error during intent extraction."""
    pass


class IntentExtractor:
    """
    Extracts structured intents from natural language agent descriptions.

    Uses LLM to parse user input and identify:
    - Triggers (what starts the agent)
    - Actions (what the agent does)
    - Conditions (filters/constraints)

    Usage:
        extractor = IntentExtractor()
        result = await extractor.extract("When I get an email, summarize it and post to Slack")
    """

    def __init__(self):
        self.settings = get_settings()
        self._logger = logger.bind(component="IntentExtractor")

        # Initialize LLM client based on provider
        if self.settings.llm_provider == "anthropic":
            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
            self._model = self.settings.default_model
        elif self.settings.llm_provider == "openai":
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
            self._model = "gpt-4-turbo-preview"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def extract(
        self,
        user_input: str,
        previous_intents: IntentExtractionResult | None = None,
    ) -> IntentExtractionResult:
        """
        Extract intents from user input.

        Args:
            user_input: Natural language description of desired agent
            previous_intents: Previous extraction result for refinement

        Returns:
            IntentExtractionResult with extracted intents
        """
        start_time = time.time()

        try:
            # Build prompt
            if previous_intents:
                prompt = REFINEMENT_PROMPT_TEMPLATE.format(
                    original_input=previous_intents.original_input,
                    previous_intents=json.dumps(
                        [i.model_dump() for i in previous_intents.all_intents],
                        default=str,
                    ),
                    new_input=user_input,
                )
            else:
                prompt = INTENT_EXTRACTION_USER_TEMPLATE.format(user_input=user_input)

            # Call LLM
            raw_response = await self._call_llm(prompt)

            # Parse response
            result = self._parse_response(raw_response, user_input)

            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            result.processing_time_ms = processing_time

            # Record metrics
            NLP_GENERATIONS_TOTAL.labels(
                tenant_id="system",
                status="success",
            ).inc()
            NLP_GENERATION_DURATION.observe(processing_time / 1000)

            self._logger.info(
                "Intent extraction completed",
                input_length=len(user_input),
                trigger_count=len(result.trigger_intents),
                action_count=len(result.action_intents),
                confidence=result.overall_confidence,
                processing_time_ms=processing_time,
            )

            return result

        except Exception as e:
            NLP_GENERATIONS_TOTAL.labels(
                tenant_id="system",
                status="error",
            ).inc()

            self._logger.error(
                "Intent extraction failed",
                error=str(e),
                input_length=len(user_input),
            )
            raise IntentExtractionError(f"Failed to extract intents: {e}") from e

    async def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call the LLM and get response."""
        if self.settings.llm_provider == "anthropic":
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=INTENT_EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
        else:  # openai
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": INTENT_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

        # Parse JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content)
        except json.JSONDecodeError as e:
            self._logger.error("Failed to parse LLM response as JSON", content=content[:500])
            raise IntentExtractionError(f"Invalid JSON response: {e}")

    def _parse_response(
        self,
        raw_response: dict[str, Any],
        original_input: str,
    ) -> IntentExtractionResult:
        """Parse raw LLM response into structured result."""
        trigger_intents = []
        action_intents = []
        condition_intents = []

        # Parse trigger intents
        for intent_data in raw_response.get("trigger_intents", []):
            intent = self._parse_intent(intent_data)
            if intent:
                trigger_intents.append(intent)

        # Parse action intents
        for intent_data in raw_response.get("action_intents", []):
            intent = self._parse_intent(intent_data)
            if intent:
                action_intents.append(intent)

        # Parse condition intents
        for intent_data in raw_response.get("condition_intents", []):
            intent = self._parse_intent(intent_data)
            if intent:
                condition_intents.append(intent)

        # Aggregate clarification questions
        all_questions = raw_response.get("clarification_questions", [])
        for intent in trigger_intents + action_intents + condition_intents:
            all_questions.extend(intent.clarification_questions)

        needs_clarification = (
            raw_response.get("needs_clarification", False) or
            len(all_questions) > 0
        )

        return IntentExtractionResult(
            original_input=original_input,
            normalized_input=raw_response.get("normalized_input", original_input),
            trigger_intents=trigger_intents,
            action_intents=action_intents,
            condition_intents=condition_intents,
            overall_confidence=raw_response.get("overall_confidence", 0.0),
            needs_clarification=needs_clarification,
            clarification_questions=list(set(all_questions)),  # Deduplicate
            raw_llm_response=raw_response,
        )

    def _parse_intent(self, intent_data: dict[str, Any]) -> ExtractedIntent | None:
        """Parse a single intent from raw data."""
        try:
            intent_type_str = intent_data.get("type", "unknown")
            try:
                intent_type = IntentType(intent_type_str)
            except ValueError:
                intent_type = IntentType.UNKNOWN

            entities = []
            for entity_data in intent_data.get("entities", []):
                entities.append(ExtractedEntity(
                    type=entity_data.get("type", "unknown"),
                    value=entity_data.get("value", ""),
                    confidence=entity_data.get("confidence", 0.5),
                ))

            return ExtractedIntent(
                type=intent_type,
                confidence=intent_data.get("confidence", 0.5),
                description=intent_data.get("description", ""),
                parameters=intent_data.get("parameters", {}),
                entities=entities,
                requires_clarification=intent_data.get("requires_clarification", False),
                clarification_questions=intent_data.get("clarification_questions", []),
                source_text=intent_data.get("source_text", ""),
            )
        except Exception as e:
            self._logger.warning("Failed to parse intent", error=str(e), data=intent_data)
            return None

    async def validate_intents(
        self,
        result: IntentExtractionResult,
    ) -> tuple[bool, list[str]]:
        """
        Validate extracted intents for completeness.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Must have at least one trigger
        if not result.has_trigger:
            issues.append("No trigger identified. What should start this agent?")

        # Must have at least one action
        if not result.has_actions:
            issues.append("No actions identified. What should the agent do?")

        # Check confidence thresholds
        for intent in result.all_intents:
            if intent.confidence < 0.5:
                issues.append(
                    f"Low confidence for {intent.type.value}: {intent.description}"
                )

        # Check for required parameters
        for intent in result.trigger_intents:
            if intent.type == IntentType.TRIGGER_ON_SCHEDULE:
                if "schedule" not in intent.parameters:
                    issues.append("Schedule trigger needs a schedule (e.g., 'daily at 9am')")
            elif intent.type == IntentType.TRIGGER_ON_EMAIL:
                if "inbox" not in intent.parameters and not intent.entities:
                    issues.append("Email trigger: which inbox or email address?")

        return len(issues) == 0, issues
```

### Step 4: Session Manager

```python
# services/agent-service/src/aswa_agents/generation/session_manager.py
"""Manages multi-turn agent creation sessions."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis

from aswa_agents.config import get_settings
from aswa_agents.generation.models import (
    AgentCreationSession,
    ConversationMessage,
    IntentExtractionResult,
)
from aswa_agents.generation.intent_extractor import IntentExtractor

logger = structlog.get_logger()


class SessionManager:
    """
    Manages multi-turn agent creation conversations.

    Stores session state in Redis and accumulates intents across turns.
    """

    SESSION_TTL_HOURS = 24

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.settings = get_settings()
        self.intent_extractor = IntentExtractor()
        self._logger = logger.bind(component="SessionManager")

    def _session_key(self, session_id: UUID) -> str:
        """Get Redis key for session."""
        return f"{self.settings.redis_prefix}session:{session_id}"

    async def create_session(
        self,
        tenant_id: str,
        user_id: str,
    ) -> AgentCreationSession:
        """Create a new agent creation session."""
        session = AgentCreationSession(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        await self._save_session(session)

        self._logger.info(
            "Created session",
            session_id=str(session.id),
            tenant_id=tenant_id,
            user_id=user_id,
        )

        return session

    async def get_session(self, session_id: UUID) -> AgentCreationSession | None:
        """Get session by ID."""
        data = await self.redis.get(self._session_key(session_id))
        if not data:
            return None
        return AgentCreationSession.model_validate_json(data)

    async def _save_session(self, session: AgentCreationSession) -> None:
        """Save session to Redis."""
        session.updated_at = datetime.utcnow()
        await self.redis.set(
            self._session_key(session.id),
            session.model_dump_json(),
            ex=timedelta(hours=self.SESSION_TTL_HOURS),
        )

    async def process_message(
        self,
        session_id: UUID,
        user_message: str,
    ) -> tuple[AgentCreationSession, str]:
        """
        Process a user message in the session.

        Returns:
            Tuple of (updated session, assistant response)
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Extract intents from new message
        previous_intents = session.accumulated_intents
        extraction_result = await self.intent_extractor.extract(
            user_message,
            previous_intents=previous_intents,
        )

        # Add user message to history
        user_msg = ConversationMessage(
            role="user",
            content=user_message,
            intents=extraction_result,
        )
        session.messages.append(user_msg)

        # Merge intents with previous
        session.accumulated_intents = self._merge_intents(
            previous_intents,
            extraction_result,
        )

        # Generate assistant response
        response = await self._generate_response(session)

        # Add assistant message to history
        assistant_msg = ConversationMessage(
            role="assistant",
            content=response,
        )
        session.messages.append(assistant_msg)

        # Update session
        await self._save_session(session)

        return session, response

    def _merge_intents(
        self,
        previous: IntentExtractionResult | None,
        new: IntentExtractionResult,
    ) -> IntentExtractionResult:
        """Merge new intents with previous ones."""
        if not previous:
            return new

        # Keep highest confidence intents
        merged_triggers = self._merge_intent_list(
            previous.trigger_intents,
            new.trigger_intents,
        )
        merged_actions = self._merge_intent_list(
            previous.action_intents,
            new.action_intents,
        )
        merged_conditions = self._merge_intent_list(
            previous.condition_intents,
            new.condition_intents,
        )

        # Calculate new overall confidence
        all_intents = merged_triggers + merged_actions + merged_conditions
        if all_intents:
            overall_confidence = sum(i.confidence for i in all_intents) / len(all_intents)
        else:
            overall_confidence = 0.0

        # Merge clarification questions
        remaining_questions = [
            q for q in previous.clarification_questions
            if q not in new.clarification_questions
        ]

        return IntentExtractionResult(
            original_input=previous.original_input,
            normalized_input=new.normalized_input,
            trigger_intents=merged_triggers,
            action_intents=merged_actions,
            condition_intents=merged_conditions,
            overall_confidence=overall_confidence,
            needs_clarification=len(remaining_questions) > 0,
            clarification_questions=remaining_questions,
        )

    def _merge_intent_list(
        self,
        previous: list,
        new: list,
    ) -> list:
        """Merge intent lists, keeping highest confidence for each type."""
        intent_map = {i.type: i for i in previous}

        for intent in new:
            if intent.type not in intent_map:
                intent_map[intent.type] = intent
            elif intent.confidence > intent_map[intent.type].confidence:
                intent_map[intent.type] = intent

        return list(intent_map.values())

    async def _generate_response(self, session: AgentCreationSession) -> str:
        """Generate assistant response based on session state."""
        intents = session.accumulated_intents
        if not intents:
            return "I'd be happy to help you create an agent! Please describe what you'd like the agent to do."

        # Check if clarification is needed
        if intents.needs_clarification:
            questions = intents.clarification_questions
            if questions:
                return f"I need a bit more information:\n\n" + "\n".join(
                    f"- {q}" for q in questions[:3]
                )

        # Validate intents
        is_valid, issues = await self.intent_extractor.validate_intents(intents)

        if not is_valid:
            return "I think I understand, but I have a few questions:\n\n" + "\n".join(
                f"- {issue}" for issue in issues[:3]
            )

        # Ready to generate agent
        return self._generate_summary(intents)

    def _generate_summary(self, intents: IntentExtractionResult) -> str:
        """Generate a summary of the understood agent."""
        parts = ["Great! Here's what I understood:\n"]

        if intents.trigger_intents:
            trigger = intents.trigger_intents[0]
            parts.append(f"**Trigger:** {trigger.description}")

        if intents.action_intents:
            parts.append("\n**Actions:**")
            for action in intents.action_intents:
                parts.append(f"  - {action.description}")

        if intents.condition_intents:
            parts.append("\n**Conditions:**")
            for condition in intents.condition_intents:
                parts.append(f"  - {condition.description}")

        confidence_pct = int(intents.overall_confidence * 100)
        parts.append(f"\n\nConfidence: {confidence_pct}%")
        parts.append("\nWould you like me to create this agent, or would you like to make changes?")

        return "\n".join(parts)

    async def complete_session(
        self,
        session_id: UUID,
    ) -> AgentCreationSession:
        """Mark session as completed."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "completed"
        await self._save_session(session)

        return session

    async def cancel_session(
        self,
        session_id: UUID,
    ) -> None:
        """Cancel and delete a session."""
        await self.redis.delete(self._session_key(session_id))
```

## Test Cases

```python
# services/agent-service/tests/unit/test_intent_extractor.py
"""Tests for intent extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_agents.generation.intent_extractor import IntentExtractor, IntentExtractionError
from aswa_agents.generation.models import IntentType, IntentExtractionResult


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"trigger_intents": [], "action_intents": [], "overall_confidence": 0.5}')]
    client.messages.create = AsyncMock(return_value=response)
    return client


class TestIntentExtractor:
    """Test IntentExtractor class."""

    async def test_extract_simple_intent(self, mock_anthropic_client):
        """Test extracting simple intent."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor.settings = MagicMock()
            extractor.settings.llm_provider = "anthropic"
            extractor._client = mock_anthropic_client
            extractor._model = "claude-3-sonnet"
            extractor._logger = MagicMock()

            # Mock response with email trigger and summarize action
            mock_response = {
                "normalized_input": "When I receive an email, summarize it",
                "trigger_intents": [
                    {
                        "type": "trigger_on_email",
                        "confidence": 0.9,
                        "description": "Trigger on email received",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": False,
                        "clarification_questions": [],
                        "source_text": "When I receive an email",
                    }
                ],
                "action_intents": [
                    {
                        "type": "action_summarize",
                        "confidence": 0.85,
                        "description": "Summarize the email content",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": False,
                        "clarification_questions": [],
                        "source_text": "summarize it",
                    }
                ],
                "condition_intents": [],
                "overall_confidence": 0.87,
                "needs_clarification": False,
                "clarification_questions": [],
            }

            import json
            mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

            result = await extractor.extract("When I receive an email, summarize it")

            assert result.has_trigger
            assert result.has_actions
            assert result.trigger_intents[0].type == IntentType.TRIGGER_ON_EMAIL
            assert result.action_intents[0].type == IntentType.ACTION_SUMMARIZE
            assert result.overall_confidence > 0.8

    async def test_extract_with_clarification_needed(self, mock_anthropic_client):
        """Test extraction that needs clarification."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor.settings = MagicMock()
            extractor.settings.llm_provider = "anthropic"
            extractor._client = mock_anthropic_client
            extractor._model = "claude-3-sonnet"
            extractor._logger = MagicMock()

            mock_response = {
                "normalized_input": "Create a ticket when something happens",
                "trigger_intents": [],
                "action_intents": [
                    {
                        "type": "action_create_ticket",
                        "confidence": 0.6,
                        "description": "Create a ticket",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": True,
                        "clarification_questions": ["What system should the ticket be created in?"],
                        "source_text": "Create a ticket",
                    }
                ],
                "condition_intents": [],
                "overall_confidence": 0.4,
                "needs_clarification": True,
                "clarification_questions": ["What should trigger this agent?"],
            }

            import json
            mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

            result = await extractor.extract("Create a ticket when something happens")

            assert result.needs_clarification
            assert len(result.clarification_questions) > 0
            assert not result.has_trigger

    async def test_validate_intents_missing_trigger(self):
        """Test validation catches missing trigger."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            result = IntentExtractionResult(
                original_input="summarize something",
                normalized_input="summarize something",
                trigger_intents=[],
                action_intents=[],
            )

            is_valid, issues = await extractor.validate_intents(result)

            assert not is_valid
            assert any("trigger" in issue.lower() for issue in issues)

    async def test_validate_intents_missing_actions(self):
        """Test validation catches missing actions."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            from aswa_agents.generation.models import ExtractedIntent

            result = IntentExtractionResult(
                original_input="when I get an email",
                normalized_input="when I get an email",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Trigger on email",
                    )
                ],
                action_intents=[],
            )

            is_valid, issues = await extractor.validate_intents(result)

            assert not is_valid
            assert any("action" in issue.lower() for issue in issues)


class TestIntentModels:
    """Test intent model classes."""

    def test_intent_extraction_result_properties(self):
        """Test IntentExtractionResult computed properties."""
        from aswa_agents.generation.models import ExtractedIntent

        result = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Email trigger",
                )
            ],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.8,
                    description="Summarize",
                )
            ],
        )

        assert result.has_trigger
        assert result.has_actions
        assert len(result.all_intents) == 2

    def test_extracted_entity_creation(self):
        """Test ExtractedEntity creation."""
        from aswa_agents.generation.models import ExtractedEntity

        entity = ExtractedEntity(
            type="email_address",
            value="test@example.com",
            confidence=0.95,
            span=(10, 26),
        )

        assert entity.type == "email_address"
        assert entity.confidence == 0.95
```

```python
# services/agent-service/tests/unit/test_session_manager.py
"""Tests for session manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aswa_agents.generation.session_manager import SessionManager
from aswa_agents.generation.models import AgentCreationSession, IntentExtractionResult


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


class TestSessionManager:
    """Test SessionManager class."""

    async def test_create_session(self, mock_redis):
        """Test creating a new session."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"
            manager.intent_extractor = MagicMock()
            manager._logger = MagicMock()

            session = await manager.create_session("tenant-1", "user-1")

            assert session.tenant_id == "tenant-1"
            assert session.user_id == "user-1"
            assert session.status == "in_progress"
            mock_redis.set.assert_called_once()

    async def test_get_session(self, mock_redis):
        """Test getting existing session."""
        session = AgentCreationSession(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        mock_redis.get.return_value = session.model_dump_json()

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            result = await manager.get_session(session.id)

            assert result is not None
            assert result.tenant_id == "tenant-1"

    async def test_get_session_not_found(self, mock_redis):
        """Test getting non-existent session."""
        mock_redis.get.return_value = None

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            result = await manager.get_session(uuid4())

            assert result is None

    def test_merge_intents(self, mock_redis):
        """Test intent merging logic."""
        from aswa_agents.generation.models import ExtractedIntent, IntentType

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)

            previous = IntentExtractionResult(
                original_input="test1",
                normalized_input="test1",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.7,
                        description="Old trigger",
                    )
                ],
            )

            new = IntentExtractionResult(
                original_input="test2",
                normalized_input="test2",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,  # Higher confidence
                        description="New trigger",
                    )
                ],
            )

            merged = manager._merge_intents(previous, new)

            # Should keep higher confidence version
            assert merged.trigger_intents[0].confidence == 0.9
            assert merged.trigger_intents[0].description == "New trigger"
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/test_intent_extractor.py -v
   pytest tests/unit/test_session_manager.py -v
   ```

2. **Test intent extraction manually:**
   ```python
   from aswa_agents.generation.intent_extractor import IntentExtractor

   extractor = IntentExtractor()
   result = await extractor.extract(
       "When I receive an email from support@example.com, summarize it and post to #support-alerts"
   )
   print(f"Triggers: {result.trigger_intents}")
   print(f"Actions: {result.action_intents}")
   print(f"Confidence: {result.overall_confidence}")
   ```

3. **Verify metrics:**
   ```bash
   curl http://localhost:9090/metrics | grep aswa_nlp
   ```

## Next Task

Proceed to `task-9.2.2-capability-matcher.md` to implement intent-to-capability matching.
