"""Tests for agent definition generator."""

import pytest
from uuid import uuid4

from aswa_agents.generation.definition_generator import AgentDefinitionGenerator, DefinitionGenerationError
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
        assert definition.actions[1].depends_on == [definition.actions[0].id]

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_generate_not_feasible_raises_error(self):
        """Test that non-feasible matches raise error."""
        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[],
            action_intents=[],
        )

        matches = CapabilityMatchResult(
            is_feasible=False,
            feasibility_issues=["No trigger", "No actions"],
        )

        generator = AgentDefinitionGenerator()

        with pytest.raises(DefinitionGenerationError):
            await generator.generate(intents, matches)

    @pytest.mark.asyncio
    async def test_generate_with_conditions(self):
        """Test generating agent with conditions."""
        intents = IntentExtractionResult(
            original_input="When email, if urgent, summarize",
            normalized_input="When email, if urgent, summarize",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email")
            ],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.9, description="Summarize")
            ],
            condition_intents=[
                ExtractedIntent(
                    type=IntentType.CONDITION_FILTER,
                    confidence=0.8,
                    description="If urgent",
                    parameters={"keyword": "urgent"},
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
                    match_score=0.9,
                    is_available=True,
                )
            ],
            condition_matches=[
                CapabilityMatch(
                    intent_id=str(uuid4()),
                    capability_id="logic_condition",
                    capability_name="Condition",
                    match_score=0.8,
                    is_available=True,
                )
            ],
            overall_feasibility=0.87,
            is_feasible=True,
        )

        generator = AgentDefinitionGenerator()
        definition = await generator.generate(intents, matches)

        assert len(definition.conditions) == 1
        assert "urgent" in definition.conditions[0].expression

    def test_generate_display_name(self):
        """Test display name generation."""
        generator = AgentDefinitionGenerator()

        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email received")
            ],
            action_intents=[
                ExtractedIntent(type=IntentType.ACTION_SUMMARIZE, confidence=0.9, description="Summarize content")
            ],
        )

        display_name = generator._generate_display_name(intents)
        assert "Email received" in display_name
        assert "Summarize content" in display_name
