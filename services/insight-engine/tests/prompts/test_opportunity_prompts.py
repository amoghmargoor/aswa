"""Tests for opportunity extraction prompts."""

import pytest
from aswa_insight.prompts.opportunity_prompts import OpportunityExtractionPrompt
from aswa_insight.prompts.base import prompt_manager
from aswa_insight.models.opportunities import OpportunityExtractionResult


class TestOpportunityExtractionPrompt:
    """Test opportunity extraction prompt template."""

    @pytest.fixture
    def template(self):
        """Get opportunity extraction template."""
        return OpportunityExtractionPrompt()

    def test_system_prompt_content(self, template):
        """Test system prompt includes required guidance."""
        system_prompt = template.get_system_prompt()

        # Check for opportunity categories
        assert "GROWTH" in system_prompt
        assert "COST_REDUCTION" in system_prompt
        assert "EFFICIENCY" in system_prompt
        assert "INNOVATION" in system_prompt
        assert "MARKET_EXPANSION" in system_prompt

        # Check for impact levels
        assert "TRANSFORMATIONAL" in system_prompt
        assert "HIGH" in system_prompt
        assert "MEDIUM" in system_prompt
        assert "LOW" in system_prompt

        # Check for effort levels
        assert "MINIMAL" in system_prompt
        assert "VERY_HIGH" in system_prompt

    def test_user_prompt_includes_text(self, template):
        """Test user prompt includes the text."""
        text = "The company could expand into emerging markets."
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "actionable business opportunities" in user_prompt.lower()

    def test_user_prompt_with_context(self, template):
        """Test context is included in prompt."""
        text = "Sample text"
        context = {
            "document_type": "strategic_plan",
            "industry": "retail",
            "company": "RetailCo",
            "strategic_priorities": ["digital_transformation", "sustainability"]
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "strategic_plan" in user_prompt
        assert "retail" in user_prompt
        assert "RetailCo" in user_prompt
        assert "digital_transformation" in user_prompt
        assert "sustainability" in user_prompt

    def test_user_prompt_without_context(self, template):
        """Test prompt works without context."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_response_model_is_correct(self, template):
        """Test response model is OpportunityExtractionResult."""
        assert template.response_model == OpportunityExtractionResult

    def test_template_attributes(self, template):
        """Test template has correct attributes."""
        assert template.name == "opportunity_extraction"
        assert template.max_tokens == 8192
        assert template.temperature == 0.0

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
        templates = prompt_manager.list_templates()
        assert "opportunity_extraction" in templates

        template = prompt_manager.get("opportunity_extraction")
        assert isinstance(template, OpportunityExtractionPrompt)

    def test_get_messages(self, template):
        """Test get_messages returns correct structure."""
        text = "Test opportunity scenario"
        messages = template.get_messages(text)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test opportunity scenario" in messages[1]["content"]

    def test_truncate_long_text(self, template):
        """Test text truncation."""
        long_text = "Opportunity: " * 50000
        user_prompt = template.get_user_prompt(long_text)

        assert len(user_prompt) < len(long_text)
        assert "[Text truncated due to length...]" in user_prompt

    def test_system_prompt_guidelines(self, template):
        """Test system prompt includes opportunity assessment guidelines."""
        system_prompt = template.get_system_prompt()

        assert "actionable" in system_prompt.lower()
        assert "impact" in system_prompt.lower()
        assert "effort" in system_prompt.lower()
        assert "confidence" in system_prompt.lower()

    def test_empty_context(self, template):
        """Test with empty context dict."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text, {})

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_partial_context(self, template):
        """Test with partial context."""
        text = "Sample text"
        context = {"industry": "technology"}
        user_prompt = template.get_user_prompt(text, context)

        assert "technology" in user_prompt
        assert "## Context" in user_prompt
