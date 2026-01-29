"""NLP agent generation endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class GenerateRequest(BaseModel):
    """Request to generate an agent from NLP prompt."""
    prompt: str
    tenant_id: str | None = None


class GenerateResponse(BaseModel):
    """Response with generated agent definition."""
    agent_definition: dict
    clarifications_needed: list[str] = []
    confidence: float


@router.post("", response_model=GenerateResponse)
async def generate_agent(request: GenerateRequest) -> GenerateResponse:
    """Generate an agent definition from natural language prompt."""
    # Implementation in Task 9.2.3
    return GenerateResponse(
        agent_definition={},
        clarifications_needed=["This feature is not yet implemented"],
        confidence=0.0,
    )


@router.post("/clarify")
async def clarify_agent(clarification_response: dict):
    """Provide clarification for agent generation."""
    # Implementation in Task 9.2.4
    return {"message": "Not implemented"}
