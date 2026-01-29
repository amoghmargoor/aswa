"""API endpoints for NLP agent generation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from aswa_agents.api.dependencies import get_current_tenant, get_current_user
from aswa_agents.generation.capability_matcher import CapabilityMatcher
from aswa_agents.generation.definition import GeneratedAgentDefinition
from aswa_agents.generation.definition_generator import AgentDefinitionGenerator
from aswa_agents.generation.intent_extractor import IntentExtractor
from aswa_agents.generation.session_manager import SessionManager


router = APIRouter()


class GenerateRequest(BaseModel):
    """Request to generate agent from NLP."""

    prompt: str = Field(..., min_length=10, max_length=2000)
    name_hint: str | None = Field(None, max_length=50)


class GenerateResponse(BaseModel):
    """Response from agent generation."""

    success: bool
    definition: GeneratedAgentDefinition | None = None
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    feasibility_issues: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class SessionResponse(BaseModel):
    """Response with session info."""

    session_id: UUID
    message: str
    is_complete: bool = False
    definition: GeneratedAgentDefinition | None = None


def get_redis() -> Redis:
    """Get Redis client."""
    from aswa_agents.config import get_settings
    import redis.asyncio as redis

    settings = get_settings()
    return redis.from_url(str(settings.redis_url))


@router.post("/from-prompt", response_model=GenerateResponse)
async def generate_from_prompt(
    request: GenerateRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user: Annotated[dict, Depends(get_current_user)],
) -> GenerateResponse:
    """Generate an agent definition from a natural language prompt."""
    try:
        extractor = IntentExtractor()
        intents = await extractor.extract(request.prompt)

        if intents.needs_clarification:
            return GenerateResponse(
                success=False,
                needs_clarification=True,
                clarification_questions=intents.clarification_questions,
                confidence=intents.overall_confidence,
            )

        # TODO: Get actual tenant connectors from integration service
        tenant_connectors = ["email", "slack", "jira"]
        matcher = CapabilityMatcher(tenant_connectors=tenant_connectors)
        matches = await matcher.match(intents)

        if not matches.is_feasible:
            return GenerateResponse(
                success=False,
                feasibility_issues=matches.feasibility_issues,
                confidence=matches.overall_feasibility,
            )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches, request.name_hint)

        return GenerateResponse(
            success=True,
            definition=definition,
            confidence=definition.generation_confidence,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session", response_model=SessionResponse)
async def create_generation_session(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user: Annotated[dict, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SessionResponse:
    """Start a new multi-turn agent creation session."""
    session_manager = SessionManager(redis)
    session = await session_manager.create_session(
        tenant_id=tenant_id,
        user_id=user["user_id"],
    )

    return SessionResponse(
        session_id=session.id,
        message="Session started. Describe the agent you want to create.",
    )


class SessionMessageRequest(BaseModel):
    """Request to send message in session."""

    message: str = Field(..., min_length=1, max_length=2000)


@router.post("/session/{session_id}/message", response_model=SessionResponse)
async def send_session_message(
    session_id: UUID,
    request: SessionMessageRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SessionResponse:
    """Send a message in an agent creation session."""
    session_manager = SessionManager(redis)

    try:
        session, response = await session_manager.process_message(session_id, request.message)

        intents = session.accumulated_intents
        is_complete = (
            intents is not None and
            intents.has_trigger and
            intents.has_actions and
            not intents.needs_clarification and
            intents.overall_confidence >= 0.7
        )

        definition = None
        if is_complete and "create" in request.message.lower():
            tenant_connectors = ["email", "slack", "jira"]
            matcher = CapabilityMatcher(tenant_connectors=tenant_connectors)
            matches = await matcher.match(intents)

            if matches.is_feasible:
                generator = AgentDefinitionGenerator()
                definition = await generator.generate(intents, matches)
                await session_manager.complete_session(session_id)

        return SessionResponse(
            session_id=session_id,
            message=response,
            is_complete=definition is not None,
            definition=definition,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/session/{session_id}")
async def cancel_session(
    session_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    """Cancel an agent creation session."""
    session_manager = SessionManager(redis)
    await session_manager.cancel_session(session_id)
    return {"cancelled": True}


class ClarificationRequest(BaseModel):
    """Request to provide clarification."""

    session_id: UUID
    answers: dict[str, str] = Field(default_factory=dict)


@router.post("/clarify")
async def clarify_agent(
    request: ClarificationRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SessionResponse:
    """Provide clarification for agent generation."""
    session_manager = SessionManager(redis)

    try:
        answers_text = ". ".join(f"{k}: {v}" for k, v in request.answers.items())
        session, response = await session_manager.process_message(
            request.session_id,
            answers_text,
        )

        return SessionResponse(
            session_id=request.session_id,
            message=response,
            is_complete=False,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
