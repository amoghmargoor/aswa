"""Tests for capability matcher."""

import pytest

from aswa_agents.generation.capability_matcher import CapabilityMatcher
from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.generation.capabilities import CapabilityCategory
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

    def test_get_nonexistent_capability(self):
        """Test getting nonexistent capability returns None."""
        cap = CapabilityRegistry.get_capability("nonexistent")
        assert cap is None

    def test_clear_registry(self):
        """Test clearing registry."""
        CapabilityRegistry.clear()
        caps = CapabilityRegistry.get_all_capabilities()
        assert len(caps) == 0


class TestCapabilityMatcher:
    """Test CapabilityMatcher class."""

    @pytest.mark.asyncio
    async def test_match_simple_intents(self):
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

    @pytest.mark.asyncio
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

        matcher = CapabilityMatcher(tenant_connectors=[])
        result = await matcher.match(intents)

        assert len(result.action_matches) == 1
        assert result.action_matches[0].is_available is False
        assert "slack" in result.action_matches[0].unavailability_reason.lower()

    @pytest.mark.asyncio
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
                    parameters={"channel": "#general", "message": "{{summary}}"},
                ),
            ],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email", "slack"])
        result = await matcher.match(intents)

        assert result.is_feasible
        assert result.overall_feasibility >= 0.6
        assert len(result.feasibility_issues) == 0

    @pytest.mark.asyncio
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
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.9,
                    description="Summarize",
                )
            ],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email"])
        result = await matcher.match(intents)

        assert "inbox" in result.trigger_matches[0].parameter_mappings
        assert result.trigger_matches[0].parameter_mappings["inbox"] == "support@test.com"

    @pytest.mark.asyncio
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

        ids = [c.id for c in available]
        assert "trigger_email" in ids
        assert "action_create_jira" in ids
        assert "action_send_slack" not in ids

    @pytest.mark.asyncio
    async def test_no_trigger_not_feasible(self):
        """Test that missing trigger makes agent not feasible."""
        intents = IntentExtractionResult(
            original_input="Summarize something",
            normalized_input="Summarize something",
            trigger_intents=[],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SUMMARIZE,
                    confidence=0.9,
                    description="Summarize",
                )
            ],
        )

        matcher = CapabilityMatcher()
        result = await matcher.match(intents)

        assert not result.is_feasible
        assert any("trigger" in issue.lower() for issue in result.feasibility_issues)

    @pytest.mark.asyncio
    async def test_no_action_not_feasible(self):
        """Test that missing action makes agent not feasible."""
        intents = IntentExtractionResult(
            original_input="When I get email",
            normalized_input="When I get email",
            trigger_intents=[
                ExtractedIntent(
                    type=IntentType.TRIGGER_ON_EMAIL,
                    confidence=0.9,
                    description="Email trigger",
                )
            ],
            action_intents=[],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email"])
        result = await matcher.match(intents)

        assert not result.is_feasible
        assert any("action" in issue.lower() for issue in result.feasibility_issues)

    @pytest.mark.asyncio
    async def test_condition_matching(self):
        """Test matching condition intents."""
        intents = IntentExtractionResult(
            original_input="When email, if urgent, summarize",
            normalized_input="When email, if urgent, summarize",
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
                )
            ],
            condition_intents=[
                ExtractedIntent(
                    type=IntentType.CONDITION_FILTER,
                    confidence=0.8,
                    description="If urgent",
                )
            ],
        )

        matcher = CapabilityMatcher(tenant_connectors=["email"])
        result = await matcher.match(intents)

        assert len(result.condition_matches) == 1
        assert result.condition_matches[0].capability_id == "logic_condition"
