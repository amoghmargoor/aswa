"""Manages multi-turn agent creation sessions."""

from datetime import datetime, timezone, timedelta
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


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class SessionManager:
    """Manages multi-turn agent creation conversations."""

    SESSION_TTL_HOURS = 24

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.settings = get_settings()
        self.intent_extractor = IntentExtractor()
        self._logger = logger.bind(component="SessionManager")

    def _session_key(self, session_id: UUID) -> str:
        """Get Redis key for session."""
        return f"{self.settings.redis_prefix}session:{session_id}"

    async def create_session(self, tenant_id: str, user_id: str) -> AgentCreationSession:
        """Create a new agent creation session."""
        session = AgentCreationSession(tenant_id=tenant_id, user_id=user_id)
        await self._save_session(session)
        self._logger.info("Created session", session_id=str(session.id), tenant_id=tenant_id, user_id=user_id)
        return session

    async def get_session(self, session_id: UUID) -> AgentCreationSession | None:
        """Get session by ID."""
        data = await self.redis.get(self._session_key(session_id))
        if not data:
            return None
        return AgentCreationSession.model_validate_json(data)

    async def _save_session(self, session: AgentCreationSession) -> None:
        """Save session to Redis."""
        session.updated_at = utcnow()
        await self.redis.set(
            self._session_key(session.id),
            session.model_dump_json(),
            ex=timedelta(hours=self.SESSION_TTL_HOURS),
        )

    async def process_message(self, session_id: UUID, user_message: str) -> tuple[AgentCreationSession, str]:
        """Process a user message in the session."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        previous_intents = session.accumulated_intents
        extraction_result = await self.intent_extractor.extract(user_message, previous_intents=previous_intents)

        user_msg = ConversationMessage(role="user", content=user_message, intents=extraction_result)
        session.messages.append(user_msg)

        session.accumulated_intents = self._merge_intents(previous_intents, extraction_result)

        response = await self._generate_response(session)

        assistant_msg = ConversationMessage(role="assistant", content=response)
        session.messages.append(assistant_msg)

        await self._save_session(session)
        return session, response

    def _merge_intents(self, previous: IntentExtractionResult | None, new: IntentExtractionResult) -> IntentExtractionResult:
        """Merge new intents with previous ones."""
        if not previous:
            return new

        merged_triggers = self._merge_intent_list(previous.trigger_intents, new.trigger_intents)
        merged_actions = self._merge_intent_list(previous.action_intents, new.action_intents)
        merged_conditions = self._merge_intent_list(previous.condition_intents, new.condition_intents)

        all_intents = merged_triggers + merged_actions + merged_conditions
        overall_confidence = sum(i.confidence for i in all_intents) / len(all_intents) if all_intents else 0.0

        remaining_questions = [q for q in previous.clarification_questions if q not in new.clarification_questions]

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

    def _merge_intent_list(self, previous: list, new: list) -> list:
        """Merge intent lists, keeping highest confidence for each type."""
        intent_map = {i.type: i for i in previous}
        for intent in new:
            if intent.type not in intent_map or intent.confidence > intent_map[intent.type].confidence:
                intent_map[intent.type] = intent
        return list(intent_map.values())

    async def _generate_response(self, session: AgentCreationSession) -> str:
        """Generate assistant response based on session state."""
        intents = session.accumulated_intents
        if not intents:
            return "I'd be happy to help you create an agent! Please describe what you'd like the agent to do."

        if intents.needs_clarification and intents.clarification_questions:
            return "I need a bit more information:\n\n" + "\n".join(f"- {q}" for q in intents.clarification_questions[:3])

        is_valid, issues = await self.intent_extractor.validate_intents(intents)
        if not is_valid:
            return "I think I understand, but I have a few questions:\n\n" + "\n".join(f"- {issue}" for issue in issues[:3])

        return self._generate_summary(intents)

    def _generate_summary(self, intents: IntentExtractionResult) -> str:
        """Generate a summary of the understood agent."""
        parts = ["Great! Here's what I understood:\n"]

        if intents.trigger_intents:
            parts.append(f"**Trigger:** {intents.trigger_intents[0].description}")

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

    async def complete_session(self, session_id: UUID) -> AgentCreationSession:
        """Mark session as completed."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        session.status = "completed"
        await self._save_session(session)
        return session

    async def cancel_session(self, session_id: UUID) -> None:
        """Cancel and delete a session."""
        await self.redis.delete(self._session_key(session_id))
