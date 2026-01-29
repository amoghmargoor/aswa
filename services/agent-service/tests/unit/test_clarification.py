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
from aswa_agents.generation.capabilities import CapabilityMatch, CapabilityMatchResult
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
            trigger_intents=[],
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
            action_intents=[],
        )

        generator = ClarificationGenerator()
        questions = generator.generate_questions(intents)

        action_questions = [q for q in questions if q.type == ClarificationType.MISSING_ACTION]
        assert len(action_questions) == 1

    def test_generate_parameter_question(self):
        """Test question generation for missing parameters."""
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
                    missing_parameters=["channel"],
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
            trigger_intents=[],
            action_intents=[
                ExtractedIntent(
                    type=IntentType.ACTION_SEND_MESSAGE,
                    confidence=0.5,
                    description="Send message",
                    requires_clarification=True,
                    clarification_questions=["Which channel?"],
                )
            ],
        )

        generator = ClarificationGenerator()
        questions = generator.generate_questions(intents)

        assert questions[0].type == ClarificationType.MISSING_TRIGGER

    def test_generate_unavailable_capability_question(self):
        """Test question for unavailable capability."""
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
                    is_available=False,
                    unavailability_reason="Missing connectors: slack",
                )
            ],
            is_feasible=False,
            overall_feasibility=0.0,
        )

        generator = ClarificationGenerator(tenant_connectors=["email"])
        questions = generator.generate_questions(intents, matches)

        option_questions = [q for q in questions if q.type == ClarificationType.MULTIPLE_OPTIONS]
        assert len(option_questions) >= 1


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

    def test_apply_action_response(self):
        """Test applying an action selection response."""
        intents = IntentExtractionResult(
            original_input="when I get email",
            normalized_input="when I get email",
            trigger_intents=[
                ExtractedIntent(type=IntentType.TRIGGER_ON_EMAIL, confidence=0.9, description="Email")
            ],
            action_intents=[],
        )

        question = ClarificationQuestion(
            type=ClarificationType.MISSING_ACTION,
            question="What should it do?",
            options=[
                ClarificationOption(id="summarize", label="Summarize", value="action_summarize"),
            ],
        )

        response = ClarificationResponse(
            question_id=question.id,
            selected_option_id="summarize",
        )

        manager = ClarificationDialogManager()
        updated = manager.apply_response(intents, question, response)

        assert len(updated.action_intents) == 1
        assert updated.has_actions

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

    def test_generate_dialog_response_no_questions(self):
        """Test response when no questions."""
        manager = ClarificationDialogManager()
        response = manager.generate_dialog_response([])

        assert "all the information" in response.lower()

    def test_apply_custom_input_response(self):
        """Test applying custom input instead of option."""
        intents = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
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
            ],
        )

        response = ClarificationResponse(
            question_id=question.id,
            custom_input="trigger_schedule",
        )

        manager = ClarificationDialogManager()
        updated = manager.apply_response(intents, question, response)

        assert len(updated.trigger_intents) == 1


class TestClarificationFlow:
    """Test complete clarification flow."""

    def test_complete_flow(self):
        """Test a complete clarification conversation."""
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

        questions = generator.generate_questions(intents)
        assert len(questions) >= 2

        trigger_q = next(q for q in questions if q.type == ClarificationType.MISSING_TRIGGER)
        trigger_response = ClarificationResponse(
            question_id=trigger_q.id,
            selected_option_id="trigger_email",
        )
        intents = manager.apply_response(intents, trigger_q, trigger_response)

        assert intents.has_trigger

        remaining = generator.generate_questions(intents)
        assert len(remaining) < len(questions)
