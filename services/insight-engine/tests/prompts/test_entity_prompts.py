"""Tests for entity extraction prompts."""

import pytest
from aswa_insight.prompts.entity_prompts import EntityExtractionPrompt
from aswa_insight.prompts.base import prompt_manager
from aswa_insight.models.entities import EntityExtractionResult


class TestEntityExtractionPrompt:
    """Test entity extraction prompt template."""

    @pytest.fixture
    def template(self):
        """Get entity extraction template."""
        return EntityExtractionPrompt()

    def test_system_prompt_content(self, template):
        """Test system prompt includes required guidance."""
        system_prompt = template.get_system_prompt()

        # Check for entity types
        assert "PERSON" in system_prompt
        assert "ORGANIZATION" in system_prompt
        assert "LOCATION" in system_prompt
        assert "TECHNOLOGY" in system_prompt
        assert "METRIC" in system_prompt

        # Check for relationship types
        assert "WORKS_FOR" in system_prompt
        assert "PARTNER_OF" in system_prompt
        assert "LOCATED_IN" in system_prompt

        # Check for guidelines
        assert "confidence" in system_prompt.lower()
        assert "Extract entities" in system_prompt

    def test_user_prompt_includes_text(self, template):
        """Test user prompt includes the text."""
        text = "Apple Inc. announced a new iPhone in Cupertino."
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "Extract all significant entities" in user_prompt

    def test_user_prompt_with_context(self, template):
        """Test context is included in prompt."""
        text = "Sample text"
        context = {
            "document_type": "earnings_report",
            "industry": "technology",
            "focus_entities": ["ORGANIZATION", "PRODUCT"]
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "earnings_report" in user_prompt
        assert "technology" in user_prompt
        assert "ORGANIZATION" in user_prompt
        assert "PRODUCT" in user_prompt

    def test_user_prompt_without_context(self, template):
        """Test prompt works without context."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_user_prompt_partial_context(self, template):
        """Test prompt with partial context."""
        text = "Sample text"
        context = {"document_type": "news_article"}
        user_prompt = template.get_user_prompt(text, context)

        assert "news_article" in user_prompt
        assert "## Context" in user_prompt

    def test_response_model_is_correct(self, template):
        """Test response model is EntityExtractionResult."""
        assert template.response_model == EntityExtractionResult

    def test_template_attributes(self, template):
        """Test template has correct attributes."""
        assert template.name == "entity_extraction"
        assert template.max_tokens == 8192
        assert template.temperature == 0.0

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
        templates = prompt_manager.list_templates()
        assert "entity_extraction" in templates

        template = prompt_manager.get("entity_extraction")
        assert isinstance(template, EntityExtractionPrompt)

    def test_get_messages(self, template):
        """Test get_messages returns correct structure."""
        text = "Test text"
        messages = template.get_messages(text)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test text" in messages[1]["content"]

    def test_truncate_long_text(self, template):
        """Test text truncation."""
        long_text = "A" * 150000
        user_prompt = template.get_user_prompt(long_text)

        assert len(user_prompt) < len(long_text)
        assert "[Text truncated due to length...]" in user_prompt

    def test_system_prompt_context_independence(self, template):
        """Test system prompt doesn't change with context."""
        prompt1 = template.get_system_prompt()
        prompt2 = template.get_system_prompt({"document_type": "test"})

        assert prompt1 == prompt2

    def test_empty_context(self, template):
        """Test with empty context dict."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text, {})

        assert text in user_prompt
        assert "## Context" not in user_prompt
