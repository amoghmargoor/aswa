"""Tests for pattern extraction prompts."""

import pytest
from aswa_insight.prompts.pattern_prompts import PatternExtractionPrompt
from aswa_insight.prompts.base import prompt_manager
from aswa_insight.models.patterns import PatternExtractionResult


class TestPatternExtractionPrompt:
    """Test pattern extraction prompt template."""

    @pytest.fixture
    def template(self):
        """Get pattern extraction template."""
        return PatternExtractionPrompt()

    def test_system_prompt_content(self, template):
        """Test system prompt includes required guidance."""
        system_prompt = template.get_system_prompt()

        # Check for pattern types
        assert "TREND" in system_prompt
        assert "CORRELATION" in system_prompt
        assert "ANOMALY" in system_prompt
        assert "CYCLE" in system_prompt
        assert "THRESHOLD" in system_prompt

        # Check for trend directions
        assert "INCREASING" in system_prompt
        assert "DECREASING" in system_prompt
        assert "STABLE" in system_prompt
        assert "VOLATILE" in system_prompt

        # Check for frequencies
        assert "DAILY" in system_prompt
        assert "WEEKLY" in system_prompt
        assert "MONTHLY" in system_prompt
        assert "QUARTERLY" in system_prompt

    def test_user_prompt_includes_text(self, template):
        """Test user prompt includes the text."""
        text = "Revenue increased by 15% over the past quarter."
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "patterns, trends, and insights" in user_prompt.lower()

    def test_user_prompt_with_context(self, template):
        """Test context is included in prompt."""
        text = "Sample text"
        context = {
            "document_type": "quarterly_report",
            "industry": "manufacturing",
            "time_period": "Q1 2024",
            "metrics_focus": ["revenue", "costs", "efficiency"]
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "quarterly_report" in user_prompt
        assert "manufacturing" in user_prompt
        assert "Q1 2024" in user_prompt
        assert "revenue" in user_prompt
        assert "costs" in user_prompt

    def test_user_prompt_without_context(self, template):
        """Test prompt works without context."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_response_model_is_correct(self, template):
        """Test response model is PatternExtractionResult."""
        assert template.response_model == PatternExtractionResult

    def test_template_attributes(self, template):
        """Test template has correct attributes."""
        assert template.name == "pattern_extraction"
        assert template.max_tokens == 8192
        assert template.temperature == 0.0

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
        templates = prompt_manager.list_templates()
        assert "pattern_extraction" in templates

        template = prompt_manager.get("pattern_extraction")
        assert isinstance(template, PatternExtractionPrompt)

    def test_get_messages(self, template):
        """Test get_messages returns correct structure."""
        text = "Test pattern data"
        messages = template.get_messages(text)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test pattern data" in messages[1]["content"]

    def test_truncate_long_text(self, template):
        """Test text truncation."""
        long_text = "Data point: " * 50000
        user_prompt = template.get_user_prompt(long_text)

        assert len(user_prompt) < len(long_text)
        assert "[Text truncated due to length...]" in user_prompt

    def test_system_prompt_guidelines(self, template):
        """Test system prompt includes pattern analysis guidelines."""
        system_prompt = template.get_system_prompt()

        assert "pattern" in system_prompt.lower()
        assert "trend" in system_prompt.lower()
        assert "anomal" in system_prompt.lower()
        assert "confidence" in system_prompt.lower()
        assert "data points" in system_prompt.lower()

    def test_empty_context(self, template):
        """Test with empty context dict."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text, {})

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_partial_context(self, template):
        """Test with partial context."""
        text = "Sample text"
        context = {"time_period": "2023-2024"}
        user_prompt = template.get_user_prompt(text, context)

        assert "2023-2024" in user_prompt
        assert "## Context" in user_prompt
