"""High-level clarification service."""

from uuid import UUID

import structlog
from redis.asyncio import Redis

from aswa_agents.generation.capability_matcher import CapabilityMatcher
from aswa_agents.generation.clarification import (
    ClarificationQuestion,
    ClarificationResponse,
)
from aswa_agents.generation.clarification_generator import (
    ClarificationDialogManager,
    ClarificationGenerator,
)
from aswa_agents.generation.intent_extractor import IntentExtractor
from aswa_agents.generation.models import IntentExtractionResult
from aswa_agents.generation.session_manager import SessionManager

logger = structlog.get_logger()


class ClarificationService:
    """Service for managing clarification dialogs."""

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
        """Process user input and generate clarifications if needed."""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        previous_intents = session.accumulated_intents
        new_intents = await self.intent_extractor.extract(user_input, previous_intents)

        matches = await self.capability_matcher.match(new_intents)

        questions = self.clarification_generator.generate_questions(new_intents, matches)

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
        """Apply a clarification response and get remaining questions."""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        intents = session.accumulated_intents
        if not intents:
            raise ValueError("No intents to clarify")

        questions = self.clarification_generator.generate_questions(intents)
        question = next((q for q in questions if q.id == response.question_id), None)

        if not question:
            raise ValueError(f"Question {response.question_id} not found")

        updated_intents = self.dialog_manager.apply_response(intents, question, response)

        matches = await self.capability_matcher.match(updated_intents)
        remaining_questions = self.clarification_generator.generate_questions(updated_intents, matches)

        return updated_intents, remaining_questions

    def _generate_ready_response(self, intents: IntentExtractionResult, matches) -> str:
        """Generate response when ready to create agent."""
        parts = ["I understand what you want:"]

        if intents.trigger_intents:
            trigger = intents.trigger_intents[0]
            parts.append(f"\n**When:** {trigger.description}")

        if intents.action_intents:
            parts.append("\n**Then:**")
            for i, action in enumerate(intents.action_intents, 1):
                parts.append(f"  {i}. {action.description}")

        confidence_pct = int(matches.overall_feasibility * 100)
        parts.append(f"\n\nConfidence: {confidence_pct}%")
        parts.append("\nSay 'create' to build this agent, or describe any changes.")

        return "\n".join(parts)


class StructuredClarificationEndpoint:
    """Provides structured clarification Q&A instead of free-form chat."""

    def __init__(self, clarification_service: ClarificationService):
        self.service = clarification_service

    async def get_next_question(self, session_id: UUID) -> ClarificationQuestion | None:
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
        """Submit answer to a clarification question."""
        response = ClarificationResponse(
            question_id=question_id,
            selected_option_id=option_id,
            custom_input=answer,
        )

        updated_intents, remaining = await self.service.apply_clarification(session_id, response)

        is_complete = len(remaining) == 0
        next_question = remaining[0] if remaining else None

        return is_complete, next_question
