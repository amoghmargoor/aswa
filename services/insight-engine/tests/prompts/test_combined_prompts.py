"""Tests for combined extraction prompts."""

import pytest
from aswa_insight.prompts.combined_prompts import (
    CombinedExtractionPrompt,
    CombinedExtractionResult,
)
from aswa_insight.prompts.base import prompt_manager


class TestCombinedExtractionResult:
    """Test combined extraction result model."""

    def test_model_fields(self):
        """Test model has all required fields."""
        result = CombinedExtractionResult(
            entities=[],
            relationships=[],
            risks=[],
            opportunities=[],
            patterns=[],
            summary="Test summary"
        )

        assert result.entities == []
        assert result.relationships == []
        assert result.risks == []
        assert result.opportunities == []
        assert result.patterns == []
        assert result.summary == "Test summary"

    def test_model_defaults(self):
        """Test model defaults for list fields."""
        result = CombinedExtractionResult(summary="Test")

        assert result.entities == []
        assert result.relationships == []
        assert result.risks == []
        assert result.opportunities == []
        assert result.patterns == []


class TestCombinedExtractionPrompt:
    """Test combined extraction prompt template."""

    @pytest.fixture
    def template(self):
        """Get combined extraction template."""
        return CombinedExtractionPrompt()

    def test_system_prompt_content(self, template):
        """Test system prompt includes all extraction types."""
        system_prompt = template.get_system_prompt()

        # Check mentions all extraction types
        assert "Entities" in system_prompt or "entities" in system_prompt.lower()
        assert "Risks" in system_prompt or "risks" in system_prompt.lower()
        assert "Opportunities" in system_prompt or "opportunities" in system_prompt.lower()
        assert "Patterns" in system_prompt or "patterns" in system_prompt.lower()

        # Check for key concepts
        assert "comprehensive" in system_prompt.lower()
        assert "confidence" in system_prompt.lower()

    def test_user_prompt_includes_text(self, template):
        """Test user prompt includes the text."""
        text = "Sample business report with entities, risks, and opportunities."
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "comprehensive analysis" in user_prompt.lower()

    def test_user_prompt_with_context(self, template):
        """Test context is included in prompt."""
        text = "Sample text"
        context = {
            "document_type": "annual_report",
            "industry": "healthcare",
            "company": "HealthCorp",
            "year": "2024"
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "annual_report" in user_prompt
        assert "healthcare" in user_prompt
        assert "HealthCorp" in user_prompt
        assert "2024" in user_prompt
        assert "## Context" in user_prompt

    def test_user_prompt_without_context(self, template):
        """Test prompt works without context."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_response_model_is_correct(self, template):
        """Test response model is CombinedExtractionResult."""
        assert template.response_model == CombinedExtractionResult

    def test_template_attributes(self, template):
        """Test template has correct attributes."""
        assert template.name == "combined_extraction"
        assert template.max_tokens == 16384  # Higher for combined extraction
        assert template.temperature == 0.0

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
        templates = prompt_manager.list_templates()
        assert "combined_extraction" in templates

        template = prompt_manager.get("combined_extraction")
        assert isinstance(template, CombinedExtractionPrompt)

    def test_get_messages(self, template):
        """Test get_messages returns correct structure."""
        text = "Test comprehensive analysis"
        messages = template.get_messages(text)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test comprehensive analysis" in messages[1]["content"]

    def test_truncate_long_text(self, template):
        """Test text truncation."""
        long_text = "Analysis: " * 50000
        user_prompt = template.get_user_prompt(long_text)

        assert len(user_prompt) < len(long_text)
        assert "[Text truncated due to length...]" in user_prompt

    def test_empty_context(self, template):
        """Test with empty context dict."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text, {})

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_context_with_none_values(self, template):
        """Test context with None values are skipped."""
        text = "Sample text"
        context = {
            "document_type": "report",
            "industry": None,
            "company": "",
            "year": "2024"
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "report" in user_prompt
        assert "2024" in user_prompt
        # None and empty values should not appear
        assert "None" not in user_prompt

    def test_user_prompt_structure(self, template):
        """Test user prompt has expected structure."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        # Should include all extraction types
        assert "entities" in user_prompt.lower()
        assert "risks" in user_prompt.lower()
        assert "opportunities" in user_prompt.lower()
        assert "patterns" in user_prompt.lower()

        # Should mention summary
        assert "summary" in user_prompt.lower()
