# Task 9.2.2: Capability Matcher

## Objective

Implement the capability matcher that maps extracted user intents to available action blocks and connectors. This ensures users can only create agents using capabilities that are actually available in their tenant.

## Prerequisites

- Task 9.2.1 completed (Intent Extraction)
- Task 9.4.4 completed (Action Block Registry) or stub available

## Implementation

### Step 1: Capability Models

```python
# services/agent-service/src/aswa_agents/generation/capabilities.py
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
```

### Step 2: Capability Registry

```python
# services/agent-service/src/aswa_agents/generation/capability_registry.py
"""Registry of available capabilities."""

from typing import Type

import structlog

from aswa_agents.generation.capabilities import Capability, CapabilityCategory
from aswa_agents.generation.models import IntentType

logger = structlog.get_logger()


class CapabilityRegistry:
    """
    Singleton registry of all available capabilities.

    Capabilities are registered from:
    1. Built-in action blocks
    2. Installed connectors
    3. Custom tenant configurations
    """

    _instance: "CapabilityRegistry | None" = None
    _capabilities: dict[str, Capability] = {}
    _initialized: bool = False

    def __new__(cls) -> "CapabilityRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls) -> None:
        """Initialize with built-in capabilities."""
        if cls._initialized:
            return

        logger.info("Initializing capability registry")

        # Register trigger capabilities
        cls._register_trigger_capabilities()

        # Register AI capabilities
        cls._register_ai_capabilities()

        # Register integration capabilities
        cls._register_integration_capabilities()

        # Register logic capabilities
        cls._register_logic_capabilities()

        cls._initialized = True
        logger.info(
            "Capability registry initialized",
            capability_count=len(cls._capabilities),
        )

    @classmethod
    def _register_trigger_capabilities(cls) -> None:
        """Register trigger capabilities."""
        triggers = [
            Capability(
                id="trigger_email",
                name="Email Trigger",
                description="Trigger when an email is received",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_EMAIL.value],
                required_connectors=["email"],
                parameter_schema={
                    "inbox": {"type": "string", "description": "Email inbox to monitor"},
                    "from_filter": {"type": "string", "description": "Filter by sender"},
                    "subject_filter": {"type": "string", "description": "Filter by subject"},
                },
                examples=[
                    "When I receive an email",
                    "When an email arrives in support@",
                    "On new email from customers",
                ],
            ),
            Capability(
                id="trigger_slack",
                name="Slack Message Trigger",
                description="Trigger on Slack messages",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_SLACK.value],
                required_connectors=["slack"],
                parameter_schema={
                    "channel": {"type": "string", "description": "Slack channel to monitor"},
                    "keyword": {"type": "string", "description": "Keyword to match"},
                },
                examples=[
                    "When someone posts in #support",
                    "On Slack message mentioning 'urgent'",
                ],
            ),
            Capability(
                id="trigger_document",
                name="Document Trigger",
                description="Trigger when a document is uploaded or updated",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_DOCUMENT.value],
                required_connectors=[],
                parameter_schema={
                    "source": {"type": "string", "description": "Document source"},
                    "file_type": {"type": "string", "description": "File type filter"},
                },
                examples=[
                    "When a document is uploaded",
                    "When a new PDF is added",
                ],
            ),
            Capability(
                id="trigger_schedule",
                name="Schedule Trigger",
                description="Trigger on a schedule",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_SCHEDULE.value],
                required_connectors=[],
                parameter_schema={
                    "schedule": {"type": "string", "description": "Cron expression or natural language"},
                },
                examples=[
                    "Every day at 9am",
                    "Weekly on Monday",
                    "Every hour",
                ],
            ),
            Capability(
                id="trigger_webhook",
                name="Webhook Trigger",
                description="Trigger on incoming webhook",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_WEBHOOK.value],
                required_connectors=[],
                parameter_schema={
                    "path": {"type": "string", "description": "Webhook path"},
                },
                examples=[
                    "When I call a webhook",
                    "On external API call",
                ],
            ),
            Capability(
                id="trigger_insight",
                name="Insight Trigger",
                description="Trigger when an insight is detected",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_INSIGHT.value],
                required_connectors=[],
                parameter_schema={
                    "insight_type": {"type": "string", "description": "Type of insight"},
                    "confidence_threshold": {"type": "number", "description": "Minimum confidence"},
                },
                examples=[
                    "When a bug is detected",
                    "When a feature request is identified",
                ],
            ),
        ]

        for cap in triggers:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_ai_capabilities(cls) -> None:
        """Register AI action capabilities."""
        ai_caps = [
            Capability(
                id="action_summarize",
                name="Summarize",
                description="Summarize content using AI",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_SUMMARIZE.value],
                required_connectors=[],
                parameter_schema={
                    "max_length": {"type": "integer", "description": "Maximum summary length"},
                    "style": {"type": "string", "enum": ["brief", "detailed", "bullet_points"]},
                },
                examples=[
                    "Summarize the email",
                    "Create a brief summary",
                    "Generate a TL;DR",
                ],
            ),
            Capability(
                id="action_extract",
                name="Extract Information",
                description="Extract specific information from content",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_EXTRACT.value],
                required_connectors=[],
                parameter_schema={
                    "extract_type": {
                        "type": "string",
                        "enum": ["entities", "action_items", "dates", "custom"],
                    },
                    "custom_fields": {"type": "array", "description": "Custom fields to extract"},
                },
                examples=[
                    "Extract action items",
                    "Find all dates mentioned",
                    "Extract customer name and issue",
                ],
            ),
            Capability(
                id="action_search",
                name="Search Knowledge Base",
                description="Search the knowledge base for relevant information",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_SEARCH.value],
                required_connectors=[],
                parameter_schema={
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                examples=[
                    "Search for similar issues",
                    "Find related documentation",
                ],
            ),
        ]

        for cap in ai_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_integration_capabilities(cls) -> None:
        """Register integration action capabilities."""
        integration_caps = [
            Capability(
                id="action_create_jira",
                name="Create Jira Ticket",
                description="Create a Jira ticket",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CREATE_TICKET.value],
                required_connectors=["jira"],
                parameter_schema={
                    "project": {"type": "string", "required": True},
                    "issue_type": {"type": "string", "default": "Task"},
                    "priority": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                examples=[
                    "Create a Jira ticket",
                    "Open a bug in Jira",
                    "Create an issue in PROJECT",
                ],
            ),
            Capability(
                id="action_create_linear",
                name="Create Linear Issue",
                description="Create a Linear issue",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CREATE_TICKET.value],
                required_connectors=["linear"],
                parameter_schema={
                    "team": {"type": "string", "required": True},
                    "priority": {"type": "integer"},
                },
                examples=[
                    "Create a Linear issue",
                    "Add to Linear backlog",
                ],
            ),
            Capability(
                id="action_send_slack",
                name="Send Slack Message",
                description="Send a message to Slack",
                category=CapabilityCategory.NOTIFICATION,
                intent_types=[IntentType.ACTION_SEND_MESSAGE.value],
                required_connectors=["slack"],
                parameter_schema={
                    "channel": {"type": "string", "required": True},
                    "message": {"type": "string", "required": True},
                    "thread_reply": {"type": "boolean", "default": False},
                },
                examples=[
                    "Post to Slack",
                    "Send message to #channel",
                    "Notify the team on Slack",
                ],
            ),
            Capability(
                id="action_send_email",
                name="Send Email",
                description="Send an email",
                category=CapabilityCategory.NOTIFICATION,
                intent_types=[IntentType.ACTION_SEND_EMAIL.value],
                required_connectors=["email"],
                parameter_schema={
                    "to": {"type": "string", "required": True},
                    "subject": {"type": "string", "required": True},
                    "body": {"type": "string", "required": True},
                },
                examples=[
                    "Send an email",
                    "Email the customer",
                    "Reply to the sender",
                ],
            ),
            Capability(
                id="action_webhook",
                name="Call Webhook",
                description="Call an external webhook",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CALL_WEBHOOK.value],
                required_connectors=[],
                parameter_schema={
                    "url": {"type": "string", "required": True},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                },
                examples=[
                    "Call a webhook",
                    "POST to external API",
                    "Trigger external system",
                ],
            ),
        ]

        for cap in integration_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_logic_capabilities(cls) -> None:
        """Register logic capabilities."""
        logic_caps = [
            Capability(
                id="logic_condition",
                name="Condition",
                description="Execute actions conditionally",
                category=CapabilityCategory.LOGIC,
                intent_types=[IntentType.CONDITION_FILTER.value, IntentType.CONDITION_MATCH.value],
                required_connectors=[],
                parameter_schema={
                    "condition": {"type": "string", "required": True},
                    "if_true": {"type": "array"},
                    "if_false": {"type": "array"},
                },
                examples=[
                    "If the email is from VIP",
                    "When priority is high",
                    "Only if contains 'urgent'",
                ],
            ),
        ]

        for cap in logic_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def get_capability(cls, capability_id: str) -> Capability | None:
        """Get capability by ID."""
        return cls._capabilities.get(capability_id)

    @classmethod
    def get_all_capabilities(cls) -> list[Capability]:
        """Get all registered capabilities."""
        return list(cls._capabilities.values())

    @classmethod
    def get_capabilities_for_intent(cls, intent_type: str) -> list[Capability]:
        """Get capabilities that can handle an intent type."""
        return [
            cap for cap in cls._capabilities.values()
            if intent_type in cap.intent_types
        ]

    @classmethod
    def get_capabilities_by_category(cls, category: CapabilityCategory) -> list[Capability]:
        """Get capabilities by category."""
        return [
            cap for cap in cls._capabilities.values()
            if cap.category == category
        ]

    @classmethod
    def clear(cls) -> None:
        """Clear registry. For testing only."""
        cls._capabilities.clear()
        cls._initialized = False
```

### Step 3: Capability Matcher Service

```python
# services/agent-service/src/aswa_agents/generation/capability_matcher.py
"""Matches user intents to available capabilities."""

from typing import Any

import structlog

from aswa_agents.generation.capabilities import (
    Capability,
    CapabilityMatch,
    CapabilityMatchResult,
)
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.models import (
    ExtractedIntent,
    IntentExtractionResult,
    IntentType,
)

logger = structlog.get_logger()


class CapabilityMatcher:
    """
    Matches extracted intents to available capabilities.

    The matcher:
    1. Finds capabilities that can handle each intent
    2. Scores the match quality
    3. Maps intent parameters to capability parameters
    4. Checks connector availability for the tenant
    """

    def __init__(self, tenant_connectors: list[str] | None = None):
        """
        Initialize matcher.

        Args:
            tenant_connectors: List of connector IDs available to the tenant
        """
        self.tenant_connectors = tenant_connectors or []
        self._logger = logger.bind(component="CapabilityMatcher")

        # Ensure registry is initialized
        CapabilityRegistry.initialize()

    async def match(
        self,
        intents: IntentExtractionResult,
    ) -> CapabilityMatchResult:
        """
        Match intents to capabilities.

        Args:
            intents: Extracted intents to match

        Returns:
            CapabilityMatchResult with matches and feasibility assessment
        """
        result = CapabilityMatchResult()

        # Match trigger intents
        for intent in intents.trigger_intents:
            match = self._match_intent(intent)
            if match:
                result.trigger_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        # Match action intents
        for intent in intents.action_intents:
            match = self._match_intent(intent)
            if match:
                result.action_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        # Match condition intents
        for intent in intents.condition_intents:
            match = self._match_intent(intent)
            if match:
                result.condition_matches.append(match)
            else:
                result.unmatched_intents.append(str(intent.id))

        # Check feasibility
        result = self._assess_feasibility(result, intents)

        self._logger.info(
            "Capability matching completed",
            trigger_matches=len(result.trigger_matches),
            action_matches=len(result.action_matches),
            unmatched=len(result.unmatched_intents),
            feasibility=result.overall_feasibility,
        )

        return result

    def _match_intent(self, intent: ExtractedIntent) -> CapabilityMatch | None:
        """Match a single intent to a capability."""
        # Find capabilities that can handle this intent type
        capabilities = CapabilityRegistry.get_capabilities_for_intent(
            intent.type.value
        )

        if not capabilities:
            self._logger.warning(
                "No capability found for intent",
                intent_type=intent.type.value,
            )
            return None

        # Score each capability and pick the best
        best_match = None
        best_score = 0.0

        for capability in capabilities:
            score, param_mappings, missing = self._score_capability(intent, capability)

            # Check connector availability
            is_available = self._check_availability(capability)

            if score > best_score:
                best_score = score
                best_match = CapabilityMatch(
                    intent_id=str(intent.id),
                    capability_id=capability.id,
                    capability_name=capability.name,
                    match_score=score,
                    parameter_mappings=param_mappings,
                    missing_parameters=missing,
                    is_available=is_available,
                    unavailability_reason="" if is_available else self._get_unavailability_reason(capability),
                )

        return best_match

    def _score_capability(
        self,
        intent: ExtractedIntent,
        capability: Capability,
    ) -> tuple[float, dict[str, str], list[str]]:
        """
        Score how well a capability matches an intent.

        Returns:
            Tuple of (score, parameter_mappings, missing_parameters)
        """
        score = 0.7  # Base score for type match

        param_mappings: dict[str, str] = {}
        missing_params: list[str] = []

        # Map intent parameters to capability parameters
        cap_params = capability.parameter_schema
        intent_params = intent.parameters

        for cap_param, schema in cap_params.items():
            if cap_param in intent_params:
                param_mappings[cap_param] = intent_params[cap_param]
                score += 0.1
            elif schema.get("required", False):
                missing_params.append(cap_param)
                score -= 0.1

        # Check entity mappings
        for entity in intent.entities:
            # Try to map entities to parameters
            for cap_param, schema in cap_params.items():
                if self._entity_matches_param(entity.type, cap_param):
                    param_mappings[cap_param] = entity.value
                    if cap_param in missing_params:
                        missing_params.remove(cap_param)
                        score += 0.1

        # Factor in intent confidence
        score *= intent.confidence

        return min(score, 1.0), param_mappings, missing_params

    def _entity_matches_param(self, entity_type: str, param_name: str) -> bool:
        """Check if an entity type can fill a parameter."""
        mappings = {
            "email_address": ["inbox", "to", "from", "from_filter"],
            "channel_name": ["channel"],
            "project_key": ["project"],
            "team_name": ["team"],
            "schedule": ["schedule"],
            "url": ["url", "webhook_url"],
        }
        return param_name in mappings.get(entity_type, [])

    def _check_availability(self, capability: Capability) -> bool:
        """Check if capability is available for tenant."""
        if not capability.required_connectors:
            return True

        return all(
            connector in self.tenant_connectors
            for connector in capability.required_connectors
        )

    def _get_unavailability_reason(self, capability: Capability) -> str:
        """Get reason why capability is unavailable."""
        missing = [
            c for c in capability.required_connectors
            if c not in self.tenant_connectors
        ]
        return f"Missing connectors: {', '.join(missing)}"

    def _assess_feasibility(
        self,
        result: CapabilityMatchResult,
        intents: IntentExtractionResult,
    ) -> CapabilityMatchResult:
        """Assess overall feasibility of the agent."""
        issues = []

        # Must have a trigger
        if not result.trigger_matches:
            issues.append("No trigger could be matched to available capabilities")

        # Must have at least one action
        if not result.action_matches:
            issues.append("No actions could be matched to available capabilities")

        # Check for unavailable capabilities
        all_matches = result.trigger_matches + result.action_matches + result.condition_matches
        unavailable = [m for m in all_matches if not m.is_available]

        for match in unavailable:
            result.unavailable_capabilities.append(match.capability_id)
            issues.append(f"{match.capability_name}: {match.unavailability_reason}")

        # Check for missing required parameters
        for match in all_matches:
            if match.missing_parameters:
                issues.append(
                    f"{match.capability_name} needs: {', '.join(match.missing_parameters)}"
                )

        # Calculate overall feasibility
        if not issues:
            avg_score = sum(m.match_score for m in all_matches) / len(all_matches) if all_matches else 0
            result.overall_feasibility = avg_score
            result.is_feasible = avg_score >= 0.6
        else:
            result.overall_feasibility = 0.0
            result.is_feasible = False

        result.feasibility_issues = issues

        return result

    def get_available_capabilities(self) -> list[Capability]:
        """Get all capabilities available to the tenant."""
        all_caps = CapabilityRegistry.get_all_capabilities()
        return [
            cap for cap in all_caps
            if self._check_availability(cap)
        ]
```

## Test Cases

```python
# services/agent-service/tests/unit/test_capability_matcher.py
"""Tests for capability matcher."""

import pytest
from uuid import uuid4

from aswa_agents.generation.capability_matcher import CapabilityMatcher
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.capabilities import Capability, CapabilityCategory
from aswa_agents.generation.models import (
    ExtractedIntent,
    ExtractedEntity,
    IntentExtractionResult,
    IntentType,
)


@pytest.fixture(autouse=True)
def init_registry():
    """Initialize capability registry before each test."""
    CapabilityRegistry.clear()
    CapabilityRegistry.initialize()
    yield
    CapabilityRegistry.clear()


class TestCapabilityRegistry:
    """Test CapabilityRegistry class."""

    def test_initialization(self):
        """Test registry initializes with capabilities."""
        caps = CapabilityRegistry.get_all_capabilities()
        assert len(caps) > 0

    def test_get_capability(self):
        """Test getting capability by ID."""
        cap = CapabilityRegistry.get_capability("trigger_email")
        assert cap is not None
        assert cap.name == "Email Trigger"

    def test_get_capabilities_for_intent(self):
        """Test finding capabilities for intent type."""
        caps = CapabilityRegistry.get_capabilities_for_intent("trigger_on_email")
        assert len(caps) >= 1
        assert any(c.id == "trigger_email" for c in caps)

    def test_get_capabilities_by_category(self):
        """Test filtering by category."""
        ai_caps = CapabilityRegistry.get_capabilities_by_category(CapabilityCategory.AI)
        assert len(ai_caps) >= 1
        assert all(c.category == CapabilityCategory.AI for c in ai_caps)


class TestCapabilityMatcher:
    """Test CapabilityMatcher class."""

    def test_match_simple_intents(self):
        """Test matching simple email + summarize intents."""
        intents = IntentExtractionResult(
            original_input="When I get an email, summarize it",
            normalized_input="When I get an email, summarize it",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Trigger on email",
                    parameters={"inbox": "support@example.com"},
                )
            ],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.85,
                    description="Summarize content",
                )
            ],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email"])
        result = await matcher.match(intents)

        assert len(result.trigger_matches) == 1
        assert len(result.action_matches) == 1
        assert result.trigger_matches[0].capability_id == "trigger_email"
        assert result.action_matches[0].capability_id == "action_summarize"

    async def test_match_with_missing_connector(self):
        """Test matching when required connector is missing."""
        intents = IntentExtractionResult(
            original_input="Post to Slack",
            normalized_input="Post to Slack",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_DOCUMENT,
                    confidence=0.9,
                    description="On document",
                )
            ],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.9,
                    description="Send to Slack",
                    parameters={"channel": "#general"},
                )
            ],
        )

        # No Slack connector available
        matcher = CapabilityMatcher(tenant_connectors=[])
        result = await matcher.match(intents)

        assert len(result.action_matches) == 1
        assert result.action_matches[0].is_available == False
        assert "slack" in result.action_matches[0].unavailability_reason.lower()

    async def test_feasibility_assessment(self):
        """Test overall feasibility is calculated correctly."""
        intents = IntentExtractionResult(
            original_input="Complete workflow",
            normalized_input="Complete workflow",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.95,
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
                    description="Send Slack",
                ),
            ],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email", "slack"])
        result = await matcher.match(intents)

        assert result.is_feasible
        assert result.overall_feasibility >= 0.6
        assert len(result.feasibility_issues) == 0

    async def test_parameter_mapping(self):
        """Test that intent parameters are mapped to capability parameters."""
        intents = IntentExtractionResult(
            original_input="Email trigger",
            normalized_input="Email trigger",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Email trigger",
                    parameters={"inbox": "support@test.com"},
                    entities=[
                        ExtractedEntity(
                            type="email_address",
                            value="support@test.com",
                            confidence=0.95,
                        )
                    ],
                )
            ],
            action_intents=[],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email"])
        result = await matcher.match(intents)

        assert "inbox" in result.trigger_matches[0].parameter_mappings
        assert result.trigger_matches[0].parameter_mappings["inbox"] == "support@test.com"

    async def test_unmatched_intents(self):
        """Test that unmatched intents are tracked."""
        intents = IntentExtractionResult(
            original_input="Do something unknown",
            normalized_input="Do something unknown",
            trigger_intents=[],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.UNKNOWN,
                    confidence=0.5,
                    description="Unknown action",
                )
            ],
        )

        matcher = CapabilityMatcher()
        result = await matcher.match(intents)

        assert len(result.unmatched_intents) > 0
        assert not result.is_feasible

    def test_get_available_capabilities(self):
        """Test getting capabilities available to tenant."""
        matcher = CapabilityMatcher(tenant_connectors=["email", "jira"])
        available = matcher.get_available_capabilities()

        # Should include email and jira capabilities
        ids = [c.id for c in available]
        assert "trigger_email" in ids
        assert "action_create_jira" in ids

        # Should not include slack capabilities
        assert "action_send_slack" not in ids
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/test_capability_matcher.py -v
   ```

2. **Test capability matching:**
   ```python
   from aswa_agents.generation.capability_matcher import CapabilityMatcher
   from aswa_agents.generation.intent_extractor import IntentExtractor

   extractor = IntentExtractor()
   intents = await extractor.extract("When I get a support email, summarize it and create a Jira ticket")

   matcher = CapabilityMatcher(tenant_connectors=["email", "jira"])
   result = await matcher.match(intents)

   print(f"Feasible: {result.is_feasible}")
   print(f"Issues: {result.feasibility_issues}")
   ```

3. **Verify registry:**
   ```python
   from aswa_agents.generation.capability_registry import CapabilityRegistry

   CapabilityRegistry.initialize()
   caps = CapabilityRegistry.get_all_capabilities()
   for cap in caps:
       print(f"{cap.id}: {cap.name} ({cap.category.value})")
   ```

## Next Task

Proceed to `task-9.2.3-agent-definition-generator.md` to implement agent definition generation.
