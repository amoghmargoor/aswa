"""Capability models and matching logic."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityCategory(str, Enum):
    """Categories of capabilities."""

    TRIGGER = "trigger"
    AI = "ai"
    INTEGRATION = "integration"
    LOGIC = "logic"
    NOTIFICATION = "notification"


class Capability(BaseModel):
    """Represents a capability that can be used in agents."""

    id: str
    name: str
    description: str
    category: CapabilityCategory
    intent_types: list[str]  # IntentType values this capability handles
    required_connectors: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)
    is_available: bool = True
    availability_reason: str = ""


class CapabilityMatch(BaseModel):
    """A match between an intent and a capability."""

    intent_id: str
    capability_id: str
    capability_name: str
    match_score: float = Field(ge=0.0, le=1.0)
    parameter_mappings: dict[str, str] = Field(default_factory=dict)
    missing_parameters: list[str] = Field(default_factory=list)
    is_available: bool = True
    unavailability_reason: str = ""


class CapabilityMatchResult(BaseModel):
    """Result of matching intents to capabilities."""

    trigger_matches: list[CapabilityMatch] = Field(default_factory=list)
    action_matches: list[CapabilityMatch] = Field(default_factory=list)
    condition_matches: list[CapabilityMatch] = Field(default_factory=list)
    unmatched_intents: list[str] = Field(default_factory=list)
    unavailable_capabilities: list[str] = Field(default_factory=list)
    overall_feasibility: float = Field(ge=0.0, le=1.0, default=0.0)
    is_feasible: bool = False
    feasibility_issues: list[str] = Field(default_factory=list)
