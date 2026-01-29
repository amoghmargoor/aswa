# Task 9.2.4: Clarification Dialog

## Objective

Implement the clarification dialog system that handles multi-turn conversations when agent requirements are ambiguous. This enables iterative refinement of agent definitions through natural conversation.

## Prerequisites

- Task 9.2.1-9.2.3 completed

## Implementation

### Step 1: Clarification Models

```python
# services/agent-service/src/aswa_agents/generation/clarification.py
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
```

### Step 2: Clarification Generator

```python
# services/agent-service/src/aswa_agents/generation/clarification_generator.py
"""Generates clarification questions from intents and matches."""

from typing import Any

import structlog

from aswa_agents.generation.capabilities import CapabilityMatchResult
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.clarification import (
    ClarificationOption,
    ClarificationQuestion,
    ClarificationType,
)
from aswa_agents.generation.models import IntentExtractionResult, IntentType

logger = structlog.get_logger()


class ClarificationGenerator:
    """
    Generates structured clarification questions.

    Analyzes intents and matches to identify what information
    is missing or ambiguous, then generates appropriate questions.
    """

    def __init__(self, tenant_connectors: list[str] | None = None):
        self.tenant_connectors = tenant_connectors or []
        self._logger = logger.bind(component="ClarificationGenerator")

    def generate_questions(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult | None = None,
    ) -> list[ClarificationQuestion]:
        """
        Generate clarification questions based on intents and matches.

        Args:
            intents: Extracted intents that may need clarification
            matches: Optional capability matches to check feasibility

        Returns:
            List of clarification questions, ordered by priority
        """
        questions = []

        # Check for missing trigger
        if not intents.has_trigger:
            questions.append(self._generate_missing_trigger_question())

        # Check for missing actions
        if not intents.has_actions:
            questions.append(self._generate_missing_action_question())

        # Check intents that need clarification
        for intent in intents.all_intents:
            if intent.requires_clarification:
                for q_text in intent.clarification_questions:
                    questions.append(self._generate_from_intent_question(intent, q_text))

        # Check matches for missing parameters and unavailable capabilities
        if matches:
            questions.extend(self._generate_from_matches(matches))

        # Sort by priority
        questions.sort(key=lambda q: q.priority, reverse=True)

        self._logger.info(
            "Generated clarification questions",
            count=len(questions),
        )

        return questions

    def _generate_missing_trigger_question(self) -> ClarificationQuestion:
        """Generate question for missing trigger."""
        available_triggers = self._get_available_triggers()

        options = [
            ClarificationOption(
                id=cap.id,
                label=cap.name,
                description=cap.description,
                value=cap.id,
                is_recommended=cap.id == "trigger_email",  # Common default
            )
            for cap in available_triggers
        ]

        return ClarificationQuestion(
            type=ClarificationType.MISSING_TRIGGER,
            question="What should trigger this agent?",
            context="I need to know when this agent should start running.",
            options=options,
            priority=10,
        )

    def _generate_missing_action_question(self) -> ClarificationQuestion:
        """Generate question for missing actions."""
        return ClarificationQuestion(
            type=ClarificationType.MISSING_ACTION,
            question="What should the agent do when triggered?",
            context="I understand when to run, but I need to know what actions to take.",
            options=[
                ClarificationOption(
                    id="summarize",
                    label="Summarize content",
                    description="Create a summary of the content",
                    value="action_summarize",
                ),
                ClarificationOption(
                    id="extract",
                    label="Extract information",
                    description="Extract specific data like action items or entities",
                    value="action_extract",
                ),
                ClarificationOption(
                    id="notify",
                    label="Send notification",
                    description="Send a message to Slack, email, or other channel",
                    value="action_send_message",
                ),
                ClarificationOption(
                    id="ticket",
                    label="Create ticket",
                    description="Create a Jira, Linear, or other issue tracker ticket",
                    value="action_create_ticket",
                ),
            ],
            priority=9,
        )

    def _generate_from_intent_question(
        self,
        intent: Any,
        question_text: str,
    ) -> ClarificationQuestion:
        """Generate question from intent's clarification need."""
        # Determine question type based on intent
        if "channel" in question_text.lower() or "where" in question_text.lower():
            q_type = ClarificationType.AMBIGUOUS_TARGET
        elif "which" in question_text.lower():
            q_type = ClarificationType.MULTIPLE_OPTIONS
        else:
            q_type = ClarificationType.MISSING_PARAMETER

        return ClarificationQuestion(
            type=q_type,
            question=question_text,
            context=f"For: {intent.description}",
            related_intent_id=str(intent.id),
            priority=5,
        )

    def _generate_from_matches(
        self,
        matches: CapabilityMatchResult,
    ) -> list[ClarificationQuestion]:
        """Generate questions from capability match issues."""
        questions = []

        all_matches = (
            matches.trigger_matches +
            matches.action_matches +
            matches.condition_matches
        )

        for match in all_matches:
            # Missing parameters
            if match.missing_parameters:
                capability = CapabilityRegistry.get_capability(match.capability_id)
                for param in match.missing_parameters:
                    schema = capability.parameter_schema.get(param, {}) if capability else {}
                    questions.append(self._generate_parameter_question(
                        match.capability_name,
                        param,
                        schema,
                        match.intent_id,
                    ))

            # Unavailable capability
            if not match.is_available:
                questions.append(ClarificationQuestion(
                    type=ClarificationType.MULTIPLE_OPTIONS,
                    question=f"'{match.capability_name}' requires {match.unavailability_reason}. Would you like to use an alternative?",
                    context="This capability isn't available with your current integrations.",
                    related_intent_id=match.intent_id,
                    options=self._get_alternative_options(match.capability_id),
                    priority=7,
                ))

        return questions

    def _generate_parameter_question(
        self,
        capability_name: str,
        param_name: str,
        schema: dict,
        intent_id: str,
    ) -> ClarificationQuestion:
        """Generate question for a missing parameter."""
        # Build user-friendly question
        param_display = param_name.replace("_", " ").title()

        if schema.get("type") == "string" and "enum" in schema:
            # Multiple choice
            options = [
                ClarificationOption(
                    id=str(i),
                    label=opt,
                    value=opt,
                )
                for i, opt in enumerate(schema["enum"])
            ]
            return ClarificationQuestion(
                type=ClarificationType.MULTIPLE_OPTIONS,
                question=f"Which {param_display} should be used for {capability_name}?",
                options=options,
                parameter_name=param_name,
                related_intent_id=intent_id,
                priority=6,
            )

        # Free text
        description = schema.get("description", f"the {param_display}")
        return ClarificationQuestion(
            type=ClarificationType.MISSING_PARAMETER,
            question=f"What {description}?",
            context=f"Needed for {capability_name}",
            parameter_name=param_name,
            related_intent_id=intent_id,
            priority=6,
        )

    def _get_available_triggers(self) -> list:
        """Get trigger capabilities available to tenant."""
        from aswa_agents.generation.capabilities import CapabilityCategory

        all_triggers = CapabilityRegistry.get_capabilities_by_category(
            CapabilityCategory.TRIGGER
        )

        return [
            cap for cap in all_triggers
            if not cap.required_connectors or
            all(c in self.tenant_connectors for c in cap.required_connectors)
        ]

    def _get_alternative_options(self, capability_id: str) -> list[ClarificationOption]:
        """Get alternative capabilities for unavailable one."""
        capability = CapabilityRegistry.get_capability(capability_id)
        if not capability:
            return []

        # Find other capabilities that handle same intent types
        alternatives = []
        for intent_type in capability.intent_types:
            for alt_cap in CapabilityRegistry.get_capabilities_for_intent(intent_type):
                if alt_cap.id != capability_id:
                    # Check if this alternative is available
                    available = all(
                        c in self.tenant_connectors
                        for c in alt_cap.required_connectors
                    )
                    if available:
                        alternatives.append(ClarificationOption(
                            id=alt_cap.id,
                            label=alt_cap.name,
                            description=alt_cap.description,
                            value=alt_cap.id,
                        ))

        return alternatives


class ClarificationDialogManager:
    """
    Manages the clarification dialog flow.

    Tracks question state, processes responses, and updates intents.
    """

    def __init__(self):
        self._logger = logger.bind(component="ClarificationDialogManager")

    def apply_response(
        self,
        intents: IntentExtractionResult,
        question: ClarificationQuestion,
        response: ClarificationResponse,
    ) -> IntentExtractionResult:
        """
        Apply a clarification response to update intents.

        Args:
            intents: Current intent extraction result
            question: The question that was answered
            response: User's response

        Returns:
            Updated IntentExtractionResult
        """
        value = response.custom_input or self._get_option_value(
            question, response.selected_option_id
        )

        if question.type == ClarificationType.MISSING_TRIGGER:
            intents = self._add_trigger_intent(intents, value)
        elif question.type == ClarificationType.MISSING_ACTION:
            intents = self._add_action_intent(intents, value)
        elif question.type == ClarificationType.MISSING_PARAMETER:
            intents = self._update_intent_parameter(
                intents,
                question.related_intent_id,
                question.parameter_name,
                value,
            )
        elif question.type == ClarificationType.AMBIGUOUS_TARGET:
            intents = self._update_intent_parameter(
                intents,
                question.related_intent_id,
                question.parameter_name or "target",
                value,
            )
        elif question.type == ClarificationType.MULTIPLE_OPTIONS:
            if question.related_intent_id:
                intents = self._replace_capability(
                    intents,
                    question.related_intent_id,
                    value,
                )

        # Remove answered clarification question
        intents.clarification_questions = [
            q for q in intents.clarification_questions
            if q != question.question
        ]

        # Update needs_clarification flag
        intents.needs_clarification = len(intents.clarification_questions) > 0

        return intents

    def _get_option_value(
        self,
        question: ClarificationQuestion,
        option_id: str | None,
    ) -> Any:
        """Get value from selected option."""
        if not option_id:
            return None

        for option in question.options:
            if option.id == option_id:
                return option.value

        return None

    def _add_trigger_intent(
        self,
        intents: IntentExtractionResult,
        trigger_type: str,
    ) -> IntentExtractionResult:
        """Add a trigger intent."""
        from aswa_agents.generation.models import ExtractedIntent

        capability = CapabilityRegistry.get_capability(trigger_type)

        # Map capability to intent type
        intent_type_str = capability.intent_types[0] if capability else "trigger_on_manual"

        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        new_intent = ExtractedIntent(
            type=intent_type,
            confidence=0.9,  # User explicitly chose this
            description=capability.description if capability else trigger_type,
            source_text="user clarification",
        )

        intents.trigger_intents.append(new_intent)
        return intents

    def _add_action_intent(
        self,
        intents: IntentExtractionResult,
        action_type: str,
    ) -> IntentExtractionResult:
        """Add an action intent."""
        from aswa_agents.generation.models import ExtractedIntent

        capability = CapabilityRegistry.get_capability(action_type)

        intent_type_str = capability.intent_types[0] if capability else "action_custom"

        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        new_intent = ExtractedIntent(
            type=intent_type,
            confidence=0.9,
            description=capability.description if capability else action_type,
            source_text="user clarification",
        )

        intents.action_intents.append(new_intent)
        return intents

    def _update_intent_parameter(
        self,
        intents: IntentExtractionResult,
        intent_id: str | None,
        param_name: str | None,
        value: Any,
    ) -> IntentExtractionResult:
        """Update a parameter on an intent."""
        if not intent_id or not param_name:
            return intents

        for intent in intents.all_intents:
            if str(intent.id) == intent_id:
                intent.parameters[param_name] = value
                intent.requires_clarification = False
                intent.clarification_questions = []
                break

        return intents

    def _replace_capability(
        self,
        intents: IntentExtractionResult,
        intent_id: str,
        new_capability_id: str,
    ) -> IntentExtractionResult:
        """Replace the capability for an intent."""
        capability = CapabilityRegistry.get_capability(new_capability_id)
        if not capability:
            return intents

        intent_type_str = capability.intent_types[0] if capability.intent_types else "unknown"

        for intent in intents.all_intents:
            if str(intent.id) == intent_id:
                try:
                    intent.type = IntentType(intent_type_str)
                except ValueError:
                    intent.type = IntentType.UNKNOWN
                intent.description = capability.description
                intent.requires_clarification = False
                break

        return intents

    def generate_dialog_response(
        self,
        questions: list[ClarificationQuestion],
    ) -> str:
        """
        Generate a natural language response with clarification questions.

        Args:
            questions: Questions to ask

        Returns:
            Natural language response string
        """
        if not questions:
            return "I have all the information I need. Would you like me to create the agent?"

        # Take top 3 questions
        top_questions = questions[:3]

        parts = ["I need a bit more information:"]

        for q in top_questions:
            if q.options:
                options_text = ", ".join(o.label for o in q.options[:4])
                parts.append(f"\n• {q.question}")
                parts.append(f"  Options: {options_text}")
            else:
                parts.append(f"\n• {q.question}")

            if q.context:
                parts.append(f"  ({q.context})")

        return "\n".join(parts)
```

### Step 3: Clarification API Integration

```python
# services/agent-service/src/aswa_agents/generation/nlp/clarification_service.py
"""High-level clarification service."""

from uuid import UUID

import structlog
from redis.asyncio import Redis

from aswa_agents.generation.capability_matcher import CapabilityMatcher
from aswa_agents.generation.clarification import (
    ClarificationQuestion,
    ClarificationResponse,
    ClarificationState,
)
from aswa_agents.generation.clarification_generator import (
    ClarificationDialogManager,
    ClarificationGenerator,
)
from aswa_agents.generation.intent_extractor import IntentExtractor
from aswa_agents.generation.models import AgentCreationSession, IntentExtractionResult
from aswa_agents.generation.session_manager import SessionManager

logger = structlog.get_logger()


class ClarificationService:
    """
    Service for managing clarification dialogs.

    Combines intent extraction, capability matching, and
    clarification generation into a cohesive flow.
    """

    def __init__(
        self,
        redis_client: Redis,
        tenant_connectors: list[str] | None = None,
    ):
        self.session_manager = SessionManager(redis_client)
        self.intent_extractor = IntentExtractor()
        self.clarification_generator = ClarificationGenerator(tenant_connectors)
        self.dialog_manager = ClarificationDialogManager()
        self.capability_matcher = CapabilityMatcher(tenant_connectors)
        self._logger = logger.bind(component="ClarificationService")

    async def process_input(
        self,
        session_id: UUID,
        user_input: str,
    ) -> tuple[IntentExtractionResult, list[ClarificationQuestion], str]:
        """
        Process user input and generate clarifications if needed.

        Args:
            session_id: Session ID
            user_input: User's message

        Returns:
            Tuple of (updated intents, pending questions, response message)
        """
        # Get current session
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Extract new intents
        previous_intents = session.accumulated_intents
        new_intents = await self.intent_extractor.extract(user_input, previous_intents)

        # Match to capabilities
        matches = await self.capability_matcher.match(new_intents)

        # Generate clarification questions
        questions = self.clarification_generator.generate_questions(new_intents, matches)

        # Generate response
        if questions:
            response = self.dialog_manager.generate_dialog_response(questions)
        elif matches.is_feasible:
            response = self._generate_ready_response(new_intents, matches)
        else:
            response = f"I couldn't match your requirements: {', '.join(matches.feasibility_issues)}"

        return new_intents, questions, response

    async def apply_clarification(
        self,
        session_id: UUID,
        response: ClarificationResponse,
    ) -> tuple[IntentExtractionResult, list[ClarificationQuestion]]:
        """
        Apply a clarification response and get remaining questions.

        Args:
            session_id: Session ID
            response: User's response to clarification

        Returns:
            Tuple of (updated intents, remaining questions)
        """
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        intents = session.accumulated_intents
        if not intents:
            raise ValueError("No intents to clarify")

        # Find the question that was answered
        questions = self.clarification_generator.generate_questions(intents)
        question = next(
            (q for q in questions if q.id == response.question_id),
            None
        )

        if not question:
            raise ValueError(f"Question {response.question_id} not found")

        # Apply the response
        updated_intents = self.dialog_manager.apply_response(intents, question, response)

        # Check for remaining questions
        matches = await self.capability_matcher.match(updated_intents)
        remaining_questions = self.clarification_generator.generate_questions(
            updated_intents, matches
        )

        return updated_intents, remaining_questions

    def _generate_ready_response(
        self,
        intents: IntentExtractionResult,
        matches,
    ) -> str:
        """Generate response when ready to create agent."""
        parts = ["I understand what you want:"]

        # Summarize trigger
        if intents.trigger_intents:
            trigger = intents.trigger_intents[0]
            parts.append(f"\n**When:** {trigger.description}")

        # Summarize actions
        if intents.action_intents:
            parts.append("\n**Then:**")
            for i, action in enumerate(intents.action_intents, 1):
                parts.append(f"  {i}. {action.description}")

        # Show confidence
        confidence_pct = int(matches.overall_feasibility * 100)
        parts.append(f"\n\nConfidence: {confidence_pct}%")
        parts.append("\nSay 'create' to build this agent, or describe any changes.")

        return "\n".join(parts)


class StructuredClarificationEndpoint:
    """
    Provides structured clarification Q&A instead of free-form chat.

    Use this when you want to present specific options to users
    rather than parsing natural language responses.
    """

    def __init__(self, clarification_service: ClarificationService):
        self.service = clarification_service

    async def get_next_question(
        self,
        session_id: UUID,
    ) -> ClarificationQuestion | None:
        """Get the next clarification question for structured UI."""
        session = await self.service.session_manager.get_session(session_id)
        if not session or not session.accumulated_intents:
            return None

        intents = session.accumulated_intents
        matches = await self.service.capability_matcher.match(intents)
        questions = self.service.clarification_generator.generate_questions(intents, matches)

        return questions[0] if questions else None

    async def submit_answer(
        self,
        session_id: UUID,
        question_id: UUID,
        answer: str | None = None,
        option_id: str | None = None,
    ) -> tuple[bool, ClarificationQuestion | None]:
        """
        Submit answer to a clarification question.

        Returns:
            Tuple of (is_complete, next_question)
        """
        response = ClarificationResponse(
            question_id=question_id,
            selected_option_id=option_id,
            custom_input=answer,
        )

        updated_intents, remaining = await self.service.apply_clarification(
            session_id, response
        )

        is_complete = len(remaining) == 0
        next_question = remaining[0] if remaining else None

        return is_complete, next_question
```

## Test Cases

```python
# services/agent-service/tests/unit/test_clarification.py
"""Tests for clarification system."""

import pytest
from uuid import uuid4

from aswa_agents.generation.clarification import (
    ClarificationQuestion,
    ClarificationResponse,
    ClarificationType,
    ClarificationOption,
)
from aswa_agents.generation.clarification_generator import (
    ClarificationDialogManager,
    ClarificationGenerator,
)
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.models import (
    ExtractedIntent,
    IntentExtractionResult,
    IntentType,
)


@pytest.fixture(autouse=True)
def init_registry():
    """Initialize capability registry."""
    CapabilityRegistry.clear()
    CapabilityRegistry.initialize()
    yield
    CapabilityRegistry.clear()


class TestClarificationGenerator:
    """Test ClarificationGenerator class."""

    def test_generate_missing_trigger_question(self):
        """Test question generation for missing trigger."""
        intents = IntentExtractionResult(
            original_input="summarize something",
            normalized_input="summarize something",
            trigger_intents=[],  # No trigger
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.9,
                    description="Summarize",
                )
            ],
        )

        generator = ClarificationGenerator(tenant_connectors=["email", "slack"])
        questions = generator.generate_questions(intents)

        # Should ask about trigger
        trigger_questions = [q for q in questions if q.type == ClarificationType.MISSING_TRIGGER]
        assert len(trigger_questions) == 1
        assert len(trigger_questions[0].options) > 0

    def test_generate_missing_action_question(self):
        """Test question generation for missing actions."""
        intents = IntentExtractionResult(
            original_input="when I get an email",
            normalized_input="when I get an email",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Email trigger",
                )
            ],
            action_intents=[],  # No actions
        )

        generator = ClarificationGenerator()
        questions = generator.generate_questions(intents)

        action_questions = [q for q in questions if q.type == ClarificationType.MISSING_ACTION]
        assert len(action_questions) == 1

    def test_generate_parameter_question(self):
        """Test question generation for missing parameters."""
        from aswa_agents.generation.capabilities import CapabilityMatch, CapabilityMatchResult

        intents = IntentExtractionResult(
            original_input="Send to Slack",
            normalized_input="Send to Slack",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email")
            ],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SEND_MESSAGE, confidence=0.9, description="Send Slack")
            ],
        )

        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_email",
                    capability_name="Email",
                    match_score=0.9,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_send_slack",
                    capability_name="Send Slack",
                    match_score=0.8,
                    missing_parameters=["channel"],  # Missing channel
                    is_available=True,
                )
            ],
            is_feasible=True,
            overall_feasibility=0.85,
        )

        generator = ClarificationGenerator(tenant_connectors=["slack"])
        questions = generator.generate_questions(intents, matches)

        param_questions = [q for q in questions if q.type == ClarificationType.MISSING_PARAMETER]
        assert len(param_questions) >= 1
        assert any("channel" in q.question.lower() for q in param_questions)

    def test_priority_ordering(self):
        """Test that questions are ordered by priority."""
        intents = IntentExtractionResult(
            original_input="do something",
            normalized_input="do something",
            trigger_intents=[],  # Missing trigger - high priority
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.5,
                    description="Send message",
                    requires_clarification=True,
                    clarification_questions=["Which channel?"],  # Lower priority
                )
            ],
        )

        generator = ClarificationGenerator()
        questions = generator.generate_questions(intents)

        # Missing trigger should come first
        assert questions[0].type == ClarificationType.MISSING_TRIGGER


class TestClarificationDialogManager:
    """Test ClarificationDialogManager class."""

    def test_apply_trigger_response(self):
        """Test applying a trigger selection response."""
        intents = IntentExtractionResult(
            original_input="summarize",
            normalized_input="summarize",
            trigger_intents=[],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.9, description="Summarize")
            ],
        )

        question = ClarificationQuestion(
            type=ClarificationType.MISSING_TRIGGER,
            question="What triggers this?",
            options=[
                ClarificationOption(id="email", label="Email", value="trigger_email"),
                ClarificationOption(id="slack", label="Slack", value="trigger_slack"),
            ],
        )

        response = ClarificationResponse(
            question_id=question.id,
            selected_option_id="email",
        )

        manager = ClarificationDialogManager()
        updated = manager.apply_response(intents, question, response)

        assert len(updated.trigger_intents) == 1
        assert updated.has_trigger

    def test_apply_parameter_response(self):
        """Test applying a parameter clarification response."""
        intent_id = uuid4()
        intents = IntentExtractionResult(
            original_input="post to slack",
            normalized_input="post to slack",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email")
            ],
            action_intents=[
                ExtractedIntent(
                    id=intent_id,
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.9,
                    description="Send Slack",
                    requires_clarification=True,
                )
            ],
        )

        question = ClarificationQuestion(
            type=ClarificationType.MISSING_PARAMETER,
            question="Which channel?",
            parameter_name="channel",
            related_intent_id=str(intent_id),
        )

        response = ClarificationResponse(
            question_id=question.id,
            custom_input="#general",
        )

        manager = ClarificationDialogManager()
        updated = manager.apply_response(intents, question, response)

        # Check parameter was added
        action_intent = updated.action_intents[0]
        assert action_intent.parameters.get("channel") == "#general"
        assert not action_intent.requires_clarification

    def test_generate_dialog_response(self):
        """Test generating natural language response."""
        questions = [
            ClarificationQuestion(
                type=ClarificationType.MISSING_TRIGGER,
                question="What should trigger this agent?",
                options=[
                    ClarificationOption(id="1", label="Email"),
                    ClarificationOption(id="2", label="Slack"),
                ],
            ),
            ClarificationQuestion(
                type=ClarificationType.MISSING_PARAMETER,
                question="Which channel should receive notifications?",
                context="For Slack notifications",
            ),
        ]

        manager = ClarificationDialogManager()
        response = manager.generate_dialog_response(questions)

        assert "trigger" in response.lower()
        assert "channel" in response.lower()
        assert "Email" in response or "email" in response


class TestClarificationFlow:
    """Test complete clarification flow."""

    async def test_complete_flow(self):
        """Test a complete clarification conversation."""
        # Start with incomplete intents
        intents = IntentExtractionResult(
            original_input="summarize and post",
            normalized_input="summarize and post",
            trigger_intents=[],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.9,
                    description="Summarize",
                ),
                ExtractedIntent(
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.8,
                    description="Post somewhere",
                    requires_clarification=True,
                    clarification_questions=["Where should I post?"],
                ),
            ],
        )

        generator = ClarificationGenerator(tenant_connectors=["email", "slack"])
        manager = ClarificationDialogManager()

        # Round 1: Get questions
        questions = generator.generate_questions(intents)
        assert len(questions) >= 2

        # Answer trigger question
        trigger_q = next(q for q in questions if q.type == ClarificationType.MISSING_TRIGGER)
        trigger_response = ClarificationResponse(
            question_id=trigger_q.id,
            selected_option_id="trigger_email",
        )
        intents = manager.apply_response(intents, trigger_q, trigger_response)

        # Now should have trigger
        assert intents.has_trigger

        # Round 2: Answer remaining questions
        remaining = generator.generate_questions(intents)
        assert len(remaining) < len(questions)  # Some resolved
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/test_clarification.py -v
   ```

2. **Test clarification flow:**
   ```python
   from aswa_agents.generation.clarification_generator import ClarificationGenerator
   from aswa_agents.generation.models import IntentExtractionResult

   intents = IntentExtractionResult(
       original_input="do something with emails",
       normalized_input="do something with emails",
       trigger_intents=[],
       action_intents=[],
   )

   generator = ClarificationGenerator(tenant_connectors=["email", "slack", "jira"])
   questions = generator.generate_questions(intents)

   for q in questions:
       print(f"Q: {q.question}")
       print(f"   Type: {q.type.value}")
       if q.options:
           print(f"   Options: {[o.label for o in q.options]}")
   ```

3. **Test dialog generation:**
   ```python
   from aswa_agents.generation.clarification_generator import ClarificationDialogManager

   manager = ClarificationDialogManager()
   response = manager.generate_dialog_response(questions)
   print(response)
   ```

## Next Task

Proceed to `task-9.3.1-nlp-builder-ui.md` to implement the NLP builder user interface.
