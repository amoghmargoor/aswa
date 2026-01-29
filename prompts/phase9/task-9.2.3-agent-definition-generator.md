# Task 9.2.3: Agent Definition Generator

## Objective

Implement the agent definition generator that transforms matched capabilities into a complete agent definition (YAML/JSON). This produces the deployable agent configuration from NLP input.

## Prerequisites

- Task 9.2.1 completed (Intent Extraction)
- Task 9.2.2 completed (Capability Matcher)

## Implementation

### Step 1: Definition Models

```python
# services/agent-service/src/aswa_agents/generation/definition.py
"""Agent definition generation models."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TriggerDefinition(BaseModel):
    """Generated trigger configuration."""

    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ConditionDefinition(BaseModel):
    """Generated condition configuration."""

    id: str = Field(default_factory=lambda: f"condition_{uuid4().hex[:8]}")
    type: str  # "expression", "match", "contains"
    expression: str
    description: str = ""


class ActionDefinition(BaseModel):
    """Generated action configuration."""

    id: str = Field(default_factory=lambda: f"action_{uuid4().hex[:8]}")
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    description: str = ""


class VariableDefinition(BaseModel):
    """Variable definition for the agent."""

    name: str
    source: str  # "trigger", "action_result", "config"
    path: str  # JSON path or expression
    default: Any = None


class ApprovalDefinition(BaseModel):
    """Approval configuration for the agent."""

    mode: str = "review"  # auto, notify, review, manual
    timeout_hours: int = 24
    reviewers: list[str] = Field(default_factory=list)
    confidence_threshold: float = 0.9


class ErrorHandlingDefinition(BaseModel):
    """Error handling configuration."""

    on_failure: str = "stop"  # stop, continue, retry
    max_retries: int = 3
    retry_delay_seconds: int = 5
    notification_channel: str | None = None


class RateLimitDefinition(BaseModel):
    """Rate limiting configuration."""

    max_executions_per_hour: int = 100
    max_executions_per_day: int = 1000


class GeneratedAgentDefinition(BaseModel):
    """Complete generated agent definition."""

    # Metadata
    name: str
    display_name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)

    # Components
    trigger: TriggerDefinition
    conditions: list[ConditionDefinition] = Field(default_factory=list)
    variables: list[VariableDefinition] = Field(default_factory=list)
    actions: list[ActionDefinition] = Field(default_factory=list)

    # Configuration
    approval: ApprovalDefinition = Field(default_factory=ApprovalDefinition)
    error_handling: ErrorHandlingDefinition = Field(default_factory=ErrorHandlingDefinition)
    rate_limit: RateLimitDefinition | None = None

    # Generation metadata
    generation_confidence: float = 0.0
    generation_notes: list[str] = Field(default_factory=list)

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        import yaml
        return yaml.dump(
            self.model_dump(exclude={"generation_confidence", "generation_notes"}),
            default_flow_style=False,
            sort_keys=False,
        )
```

### Step 2: Definition Generator

```python
# services/agent-service/src/aswa_agents/generation/definition_generator.py
"""Generates agent definitions from matched capabilities."""

import re
from typing import Any
from uuid import uuid4

import structlog

from aswa_agents.generation.capabilities import CapabilityMatch, CapabilityMatchResult
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.definition import (
    ActionDefinition,
    ApprovalDefinition,
    ConditionDefinition,
    ErrorHandlingDefinition,
    GeneratedAgentDefinition,
    TriggerDefinition,
    VariableDefinition,
)
from aswa_agents.generation.models import ExtractedIntent, IntentExtractionResult

logger = structlog.get_logger()


class DefinitionGenerationError(Exception):
    """Error during definition generation."""
    pass


class AgentDefinitionGenerator:
    """
    Generates complete agent definitions from matched capabilities.

    The generator:
    1. Creates trigger configuration from trigger matches
    2. Builds action chain from action matches
    3. Sets up variables for data flow between actions
    4. Configures approval based on confidence levels
    """

    def __init__(self):
        self._logger = logger.bind(component="DefinitionGenerator")

    async def generate(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
        name_hint: str | None = None,
    ) -> GeneratedAgentDefinition:
        """
        Generate agent definition from intents and capability matches.

        Args:
            intents: Original extracted intents
            matches: Capability match results
            name_hint: Optional hint for agent name

        Returns:
            GeneratedAgentDefinition ready for deployment
        """
        if not matches.is_feasible:
            raise DefinitionGenerationError(
                f"Cannot generate: {', '.join(matches.feasibility_issues)}"
            )

        # Generate name and description
        name = self._generate_name(intents, name_hint)
        display_name = self._generate_display_name(intents)
        description = self._generate_description(intents)

        # Generate trigger
        trigger = self._generate_trigger(matches.trigger_matches[0], intents.trigger_intents[0])

        # Generate conditions
        conditions = self._generate_conditions(matches.condition_matches, intents.condition_intents)

        # Generate actions
        actions = self._generate_actions(matches.action_matches, intents.action_intents)

        # Generate variables for data flow
        variables = self._generate_variables(trigger, actions)

        # Generate approval config based on confidence
        approval = self._generate_approval_config(matches)

        # Generate tags
        tags = self._generate_tags(intents, matches)

        # Create definition
        definition = GeneratedAgentDefinition(
            name=name,
            display_name=display_name,
            description=description,
            trigger=trigger,
            conditions=conditions,
            variables=variables,
            actions=actions,
            approval=approval,
            tags=tags,
            generation_confidence=matches.overall_feasibility,
            generation_notes=self._generate_notes(intents, matches),
        )

        self._logger.info(
            "Generated agent definition",
            name=name,
            action_count=len(actions),
            confidence=matches.overall_feasibility,
        )

        return definition

    def _generate_name(
        self,
        intents: IntentExtractionResult,
        hint: str | None,
    ) -> str:
        """Generate a valid agent name."""
        if hint:
            # Sanitize hint
            name = re.sub(r'[^a-z0-9-]', '-', hint.lower())
            name = re.sub(r'-+', '-', name).strip('-')
            return name[:50]

        # Generate from intents
        parts = []

        if intents.trigger_intents:
            trigger_type = intents.trigger_intents[0].type.value
            parts.append(trigger_type.replace("trigger_on_", ""))

        if intents.action_intents:
            action_type = intents.action_intents[0].type.value
            parts.append(action_type.replace("action_", ""))

        if parts:
            base = "-".join(parts)
        else:
            base = "generated"

        # Add unique suffix
        suffix = uuid4().hex[:6]
        return f"{base}-{suffix}"

    def _generate_display_name(self, intents: IntentExtractionResult) -> str:
        """Generate human-readable display name."""
        parts = []

        if intents.trigger_intents:
            trigger = intents.trigger_intents[0]
            parts.append(trigger.description or "Trigger")

        if intents.action_intents:
            actions = [a.description or a.type.value for a in intents.action_intents]
            parts.append(" & ".join(actions[:2]))

        if parts:
            return " → ".join(parts)

        return "Generated Agent"

    def _generate_description(self, intents: IntentExtractionResult) -> str:
        """Generate agent description."""
        return intents.normalized_input or intents.original_input

    def _generate_trigger(
        self,
        match: CapabilityMatch,
        intent: ExtractedIntent,
    ) -> TriggerDefinition:
        """Generate trigger configuration."""
        capability = CapabilityRegistry.get_capability(match.capability_id)

        config = dict(match.parameter_mappings)

        # Add defaults from capability schema
        if capability:
            for param, schema in capability.parameter_schema.items():
                if param not in config and "default" in schema:
                    config[param] = schema["default"]

        return TriggerDefinition(
            type=match.capability_id.replace("trigger_", ""),
            config=config,
        )

    def _generate_conditions(
        self,
        matches: list[CapabilityMatch],
        intents: list[ExtractedIntent],
    ) -> list[ConditionDefinition]:
        """Generate condition configurations."""
        conditions = []

        for match, intent in zip(matches, intents):
            condition = ConditionDefinition(
                type="expression",
                expression=self._build_condition_expression(intent),
                description=intent.description,
            )
            conditions.append(condition)

        return conditions

    def _build_condition_expression(self, intent: ExtractedIntent) -> str:
        """Build condition expression from intent."""
        # Simple expression builder based on intent parameters
        params = intent.parameters

        if "keyword" in params:
            return f'contains(trigger.content, "{params["keyword"]}")'
        elif "from_filter" in params:
            return f'trigger.from == "{params["from_filter"]}"'
        elif "priority" in params:
            return f'trigger.priority == "{params["priority"]}"'

        return "true"  # Default to always true

    def _generate_actions(
        self,
        matches: list[CapabilityMatch],
        intents: list[ExtractedIntent],
    ) -> list[ActionDefinition]:
        """Generate action configurations."""
        actions = []
        previous_id = None

        for i, (match, intent) in enumerate(zip(matches, intents)):
            capability = CapabilityRegistry.get_capability(match.capability_id)

            action_id = f"action_{i+1}"

            config = dict(match.parameter_mappings)

            # Add template variables for dynamic content
            config = self._add_template_variables(config, match, intent)

            # Set up dependencies
            depends_on = [previous_id] if previous_id else []

            action = ActionDefinition(
                id=action_id,
                type=match.capability_id.replace("action_", ""),
                config=config,
                depends_on=depends_on,
                description=intent.description,
            )
            actions.append(action)
            previous_id = action_id

        return actions

    def _add_template_variables(
        self,
        config: dict[str, Any],
        match: CapabilityMatch,
        intent: ExtractedIntent,
    ) -> dict[str, Any]:
        """Add template variables for dynamic content."""
        # For summarize actions, reference trigger content
        if "summarize" in match.capability_id:
            if "content" not in config:
                config["content"] = "{{ trigger.content }}"

        # For message actions, set up template
        if "send" in match.capability_id or "message" in match.capability_id:
            if "message" not in config:
                config["message"] = "{{ actions.action_1.result }}"

        # For ticket creation, set up title/description
        if "create" in match.capability_id and "ticket" in match.capability_id:
            if "title" not in config:
                config["title"] = "{{ trigger.subject | default: 'New Issue' }}"
            if "description" not in config:
                config["description"] = "{{ trigger.content }}"

        return config

    def _generate_variables(
        self,
        trigger: TriggerDefinition,
        actions: list[ActionDefinition],
    ) -> list[VariableDefinition]:
        """Generate variable definitions for data flow."""
        variables = []

        # Always include trigger content
        variables.append(VariableDefinition(
            name="trigger_content",
            source="trigger",
            path="content",
        ))

        # Add action result variables
        for action in actions:
            variables.append(VariableDefinition(
                name=f"{action.id}_result",
                source="action_result",
                path=f"{action.id}.result",
            ))

        return variables

    def _generate_approval_config(
        self,
        matches: CapabilityMatchResult,
    ) -> ApprovalDefinition:
        """Generate approval configuration based on confidence."""
        confidence = matches.overall_feasibility

        if confidence >= 0.95:
            mode = "auto"
        elif confidence >= 0.85:
            mode = "notify"
        elif confidence >= 0.7:
            mode = "review"
        else:
            mode = "manual"

        return ApprovalDefinition(
            mode=mode,
            confidence_threshold=confidence,
        )

    def _generate_tags(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
    ) -> list[str]:
        """Generate tags for the agent."""
        tags = ["generated"]

        # Add trigger type tag
        if matches.trigger_matches:
            trigger_type = matches.trigger_matches[0].capability_id.replace("trigger_", "")
            tags.append(trigger_type)

        # Add integration tags
        for match in matches.action_matches:
            capability = CapabilityRegistry.get_capability(match.capability_id)
            if capability and capability.required_connectors:
                tags.extend(capability.required_connectors)

        return list(set(tags))

    def _generate_notes(
        self,
        intents: IntentExtractionResult,
        matches: CapabilityMatchResult,
    ) -> list[str]:
        """Generate notes about the generation."""
        notes = []

        # Note any missing parameters
        for match in matches.trigger_matches + matches.action_matches:
            if match.missing_parameters:
                notes.append(
                    f"{match.capability_name}: Missing {', '.join(match.missing_parameters)}"
                )

        # Note confidence levels
        if matches.overall_feasibility < 0.8:
            notes.append("Review recommended due to lower confidence")

        return notes
```

### Step 3: Generation API Endpoint

```python
# services/agent-service/src/aswa_agents/api/endpoints/generation.py
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
    """
    Generate an agent definition from a natural language prompt.

    This is a single-turn generation - for multi-turn conversations,
    use the session-based endpoints.
    """
    try:
        # Extract intents
        extractor = IntentExtractor()
        intents = await extractor.extract(request.prompt)

        # Check if clarification needed
        if intents.needs_clarification:
            return GenerateResponse(
                success=False,
                needs_clarification=True,
                clarification_questions=intents.clarification_questions,
                confidence=intents.overall_confidence,
            )

        # Match to capabilities
        # TODO: Get actual tenant connectors from integration service
        tenant_connectors = ["email", "slack", "jira"]  # Placeholder
        matcher = CapabilityMatcher(tenant_connectors=tenant_connectors)
        matches = await matcher.match(intents)

        # Check feasibility
        if not matches.is_feasible:
            return GenerateResponse(
                success=False,
                feasibility_issues=matches.feasibility_issues,
                confidence=matches.overall_feasibility,
            )

        # Generate definition
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
        session, response = await session_manager.process_message(
            session_id,
            request.message,
        )

        # Check if ready to generate
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
            # User confirmed, generate definition
            tenant_connectors = ["email", "slack", "jira"]  # Placeholder
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
```

## Test Cases

```python
# services/agent-service/tests/unit/test_definition_generator.py
"""Tests for agent definition generator."""

import pytest
from uuid import uuid4

from aswa_agents.generation.definition_generator import AgentDefinitionGenerator
from aswa_agents.generation.capabilities import CapabilityMatch, CapabilityMatchResult
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


class TestAgentDefinitionGenerator:
    """Test AgentDefinitionGenerator class."""

    async def test_generate_simple_agent(self):
        """Test generating a simple email → summarize agent."""
        intents = IntentExtractionResult(
            original_input="When I get an email, summarize it",
            normalized_input="When I get an email, summarize it",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Trigger on email received",
                )
            ],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.85,
                    description="Summarize the content",
                )
            ],
        )

        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_email",
                    capability_name="Email Trigger",
                    match_score=0.9,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_summarize",
                    capability_name="Summarize",
                    match_score=0.85,
                    is_available=True,
                )
            ],
            overall_feasibility=0.87,
            is_feasible=True,
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        assert definition.name is not None
        assert definition.trigger.type == "email"
        assert len(definition.actions) == 1
        assert definition.actions[0].type == "summarize"

    async def test_generate_with_multiple_actions(self):
        """Test generating agent with multiple chained actions."""
        intents = IntentExtractionResult(
            original_input="Summarize emails and post to Slack",
            normalized_input="Summarize emails and post to Slack",
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
                    confidence=0.9,
                    description="Summarize",
                ),
                ExtractedIntent(
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.85,
                    description="Post to Slack",
                    parameters={"channel": "#general"},
                ),
            ],
        )

        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_email",
                    capability_name="Email Trigger",
                    match_score=0.9,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_summarize",
                    capability_name="Summarize",
                    match_score=0.9,
                    is_available=True,
                ),
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_send_slack",
                    capability_name="Send Slack Message",
                    match_score=0.85,
                    parameter_mappings={"channel": "#general"},
                    is_available=True,
                ),
            ],
            overall_feasibility=0.87,
            is_feasible=True,
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        assert len(definition.actions) == 2
        # Second action should depend on first
        assert definition.actions[1].depends_on == [definition.actions[0].id]

    async def test_generate_approval_config_high_confidence(self):
        """Test high confidence results in auto approval."""
        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_DOCUMENT,
                    confidence=0.98,
                    description="Document trigger",
                )
            ],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.97,
                    description="Summarize",
                )
            ],
        )

        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_document",
                    capability_name="Document Trigger",
                    match_score=0.98,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_summarize",
                    capability_name="Summarize",
                    match_score=0.97,
                    is_available=True,
                )
            ],
            overall_feasibility=0.97,
            is_feasible=True,
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        assert definition.approval.mode == "auto"

    async def test_generate_approval_config_low_confidence(self):
        """Test low confidence results in manual approval."""
        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_document",
                    capability_name="Document Trigger",
                    match_score=0.65,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_summarize",
                    capability_name="Summarize",
                    match_score=0.6,
                    is_available=True,
                )
            ],
            overall_feasibility=0.62,
            is_feasible=True,
        )

        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[ExtractedIntent(type=IntentType.TRIGGER_ON_DOCUMENT, confidence=0.65, description="t")],
            action_intents=[ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.6, description="t")],
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        assert definition.approval.mode == "manual"

    async def test_generate_yaml_output(self):
        """Test YAML generation."""
        intents = IntentExtractionResult(
            original_input="Email to summary",
            normalized_input="Email to summary",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email")
            ],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.9, description="Summarize")
            ],
        )

        matches = CapabilityMatchResult(
            trigger_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="trigger_email",
                    capability_name="Email Trigger",
                    match_score=0.9,
                    is_available=True,
                )
            ],
            action_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="action_summarize",
                    capability_name="Summarize",
                    match_score=0.9,
                    is_available=True,
                )
            ],
            overall_feasibility=0.9,
            is_feasible=True,
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        yaml_output = definition.to_yaml()
        assert "trigger:" in yaml_output
        assert "actions:" in yaml_output
        assert "email" in yaml_output

    def test_generate_name_from_hint(self):
        """Test name generation from hint."""
        generator = AgentDefinitionGenerator()

        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[],
            action_intents=[],
        )

        name = generator._generate_name(intents, "My Cool Agent!")
        assert name == "my-cool-agent"
        assert len(name) <= 50

    def test_generate_name_from_intents(self):
        """Test name generation from intents."""
        generator = AgentDefinitionGenerator()

        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="t")
            ],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.9, description="t")
            ],
        )

        name = generator._generate_name(intents, None)
        assert "email" in name
        assert "summarize" in name
```

```python
# services/agent-service/tests/integration/test_generation_api.py
"""Integration tests for generation API."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestGenerationAPI:
    """Test generation API endpoints."""

    async def test_generate_from_prompt(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test single-turn generation."""
        response = await async_client.post(
            "/api/v1/generate/from-prompt",
            json={
                "prompt": "When I receive a support email, summarize it and create a Jira ticket",
                "name_hint": "support-handler",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        if data["success"]:
            assert data["definition"] is not None
            assert "trigger" in data["definition"]
            assert "actions" in data["definition"]
        else:
            # Either needs clarification or has feasibility issues
            assert data["needs_clarification"] or len(data["feasibility_issues"]) > 0

    async def test_create_session(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test creating a generation session."""
        response = await async_client.post(
            "/api/v1/generate/session",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["message"] is not None

    async def test_session_conversation(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test multi-turn session conversation."""
        # Create session
        create_response = await async_client.post(
            "/api/v1/generate/session",
            headers=auth_headers,
        )
        session_id = create_response.json()["session_id"]

        # First message
        msg1_response = await async_client.post(
            f"/api/v1/generate/session/{session_id}/message",
            json={"message": "I want to summarize emails"},
            headers=auth_headers,
        )
        assert msg1_response.status_code == 200

        # Follow-up
        msg2_response = await async_client.post(
            f"/api/v1/generate/session/{session_id}/message",
            json={"message": "And post the summary to Slack #general"},
            headers=auth_headers,
        )
        assert msg2_response.status_code == 200
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/test_definition_generator.py -v
   ```

2. **Run integration tests:**
   ```bash
   pytest tests/integration/test_generation_api.py -v --integration
   ```

3. **Test generation manually:**
   ```bash
   curl -X POST http://localhost:8090/api/v1/generate/from-prompt \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "When I get a support email, summarize it and post to #support channel"}'
   ```

4. **Verify YAML output:**
   ```python
   from aswa_agents.generation.definition import GeneratedAgentDefinition

   definition = GeneratedAgentDefinition(...)
   print(definition.to_yaml())
   ```

## Next Task

Proceed to `task-9.2.4-clarification-dialog.md` to implement the clarification conversation flow.
