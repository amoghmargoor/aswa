"""Tests for intent extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from aswa_agents.generation.intent_extractor import IntentExtractor, IntentExtractionError
from aswa_agents.generation.models import IntentType, IntentExtractionResult, ExtractedIntent, ExtractedEntity


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"trigger_intents": [], "action_intents": [], "overall_confidence": 0.5}')]
    client.messages.create = AsyncMock(return_value=response)
    return client


class TestIntentExtractor:
    """Test IntentExtractor class."""

    @pytest.mark.asyncio
    async def test_extract_simple_intent(self, mock_anthropic_client):
        """Test extracting simple intent."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor.settings = MagicMock()
            extractor.settings.llm_provider = "anthropic"
            extractor._client = mock_anthropic_client
            extractor._model = "claude-3-sonnet"
            extractor._logger = MagicMock()

            mock_response = {
                "normalized_input": "When I receive an email, summarize it",
                "trigger_intents": [
                    {
                        "type": "trigger_on_email",
                        "confidence": 0.9,
                        "description": "Trigger on email received",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": False,
                        "clarification_questions": [],
                        "source_text": "When I receive an email",
                    }
                ],
                "action_intents": [
                    {
                        "type": "action_summarize",
                        "confidence": 0.85,
                        "description": "Summarize the email content",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": False,
                        "clarification_questions": [],
                        "source_text": "summarize it",
                    }
                ],
                "condition_intents": [],
                "overall_confidence": 0.87,
                "needs_clarification": False,
                "clarification_questions": [],
            }

            mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

            result = await extractor.extract("When I receive an email, summarize it")

            assert result.has_trigger
            assert result.has_actions
            assert result.trigger_intents[0].type == IntentType.TRIGGER_ON_EMAIL
            assert result.action_intents[0].type == IntentType.ACTION_SUMMARIZE
            assert result.overall_confidence > 0.8

    @pytest.mark.asyncio
    async def test_extract_with_clarification_needed(self, mock_anthropic_client):
        """Test extraction that needs clarification."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor.settings = MagicMock()
            extractor.settings.llm_provider = "anthropic"
            extractor._client = mock_anthropic_client
            extractor._model = "claude-3-sonnet"
            extractor._logger = MagicMock()

            mock_response = {
                "normalized_input": "Create a ticket when something happens",
                "trigger_intents": [],
                "action_intents": [
                    {
                        "type": "action_create_ticket",
                        "confidence": 0.6,
                        "description": "Create a ticket",
                        "parameters": {},
                        "entities": [],
                        "requires_clarification": True,
                        "clarification_questions": ["What system should the ticket be created in?"],
                        "source_text": "Create a ticket",
                    }
                ],
                "condition_intents": [],
                "overall_confidence": 0.4,
                "needs_clarification": True,
                "clarification_questions": ["What should trigger this agent?"],
            }

            mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

            result = await extractor.extract("Create a ticket when something happens")

            assert result.needs_clarification
            assert len(result.clarification_questions) > 0
            assert not result.has_trigger

    @pytest.mark.asyncio
    async def test_validate_intents_missing_trigger(self):
        """Test validation catches missing trigger."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            result = IntentExtractionResult(
                original_input="summarize something",
                normalized_input="summarize something",
                trigger_intents=[],
                action_intents=[],
            )

            is_valid, issues = await extractor.validate_intents(result)

            assert not is_valid
            assert any("trigger" in issue.lower() for issue in issues)

    @pytest.mark.asyncio
    async def test_validate_intents_missing_actions(self):
        """Test validation catches missing actions."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            result = IntentExtractionResult(
                original_input="when I get an email",
                normalized_input="when I get an email",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Trigger on email",
                    )
                ],
                action_intents=[],
            )

            is_valid, issues = await extractor.validate_intents(result)

            assert not is_valid
            assert any("action" in issue.lower() for issue in issues)

    @pytest.mark.asyncio
    async def test_validate_intents_schedule_missing_schedule(self):
        """Test validation catches schedule trigger without schedule."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            result = IntentExtractionResult(
                original_input="run periodically and summarize",
                normalized_input="run periodically and summarize",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_SCHEDULE,
                        confidence=0.9,
                        description="Trigger on schedule",
                        parameters={},
                    )
                ],
                action_intents=[
                    ExtractedIntent(
                        type=IntentType.ACTION_SUMMARIZE,
                        confidence=0.9,
                        description="Summarize content",
                    )
                ],
            )

            is_valid, issues = await extractor.validate_intents(result)

            assert not is_valid
            assert any("schedule" in issue.lower() for issue in issues)

    @pytest.mark.asyncio
    async def test_validate_intents_valid(self):
        """Test validation passes for valid intents."""
        with patch.object(IntentExtractor, '__init__', lambda x: None):
            extractor = IntentExtractor()
            extractor._logger = MagicMock()

            result = IntentExtractionResult(
                original_input="when I get an email, summarize it",
                normalized_input="when I get an email, summarize it",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Trigger on email",
                        entities=[ExtractedEntity(type="email", value="test@test.com", confidence=0.9)],
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

            is_valid, issues = await extractor.validate_intents(result)

            assert is_valid
            assert len(issues) == 0


class TestIntentModels:
    """Test intent model classes."""

    def test_intent_extraction_result_properties(self):
        """Test IntentExtractionResult computed properties."""
        result = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
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
                    confidence=0.8,
                    description="Summarize",
                )
            ],
        )

        assert result.has_trigger
        assert result.has_actions
        assert len(result.all_intents) == 2

    def test_extracted_entity_creation(self):
        """Test ExtractedEntity creation."""
        entity = ExtractedEntity(
            type="email_address",
            value="test@example.com",
            confidence=0.95,
            span=(10, 26),
        )

        assert entity.type == "email_address"
        assert entity.confidence == 0.95

    def test_intent_type_enum_values(self):
        """Test IntentType enum has expected values."""
        assert IntentType.TRIGGER_ON_EMAIL.value == "trigger_on_email"
        assert IntentType.ACTION_SUMMARIZE.value == "action_summarize"
        assert IntentType.CONDITION_FILTER.value == "condition_filter"
        assert IntentType.UNKNOWN.value == "unknown"

    def test_intent_extraction_result_no_intents(self):
        """Test IntentExtractionResult with no intents."""
        result = IntentExtractionResult(
            original_input="test",
            normalized_input="test",
        )

        assert not result.has_trigger
        assert not result.has_actions
        assert len(result.all_intents) == 0
