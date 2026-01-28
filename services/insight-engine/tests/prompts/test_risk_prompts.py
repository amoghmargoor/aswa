"""Tests for risk extraction prompts."""

import pytest
from aswa_insight.prompts.risk_prompts import RiskExtractionPrompt
from aswa_insight.prompts.base import prompt_manager
from aswa_insight.models.risks import RiskExtractionResult


class TestRiskExtractionPrompt:
    """Test risk extraction prompt template."""

    @pytest.fixture
    def template(self):
        """Get risk extraction template."""
        return RiskExtractionPrompt()

    def test_system_prompt_content(self, template):
        """Test system prompt includes required guidance."""
        system_prompt = template.get_system_prompt()

        # Check for risk categories
        assert "FINANCIAL" in system_prompt
        assert "OPERATIONAL" in system_prompt
        assert "STRATEGIC" in system_prompt
        assert "SECURITY" in system_prompt
        assert "COMPLIANCE" in system_prompt

        # Check for severity levels
        assert "CRITICAL" in system_prompt
        assert "HIGH" in system_prompt
        assert "MEDIUM" in system_prompt
        assert "LOW" in system_prompt

        # Check for likelihood levels
        assert "ALMOST_CERTAIN" in system_prompt
        assert "LIKELY" in system_prompt
        assert "POSSIBLE" in system_prompt
        assert "UNLIKELY" in system_prompt

        # Check for time horizons
        assert "IMMEDIATE" in system_prompt
        assert "SHORT_TERM" in system_prompt
        assert "MEDIUM_TERM" in system_prompt
        assert "LONG_TERM" in system_prompt

    def test_user_prompt_includes_text(self, template):
        """Test user prompt includes the text."""
        text = "The company faces significant cybersecurity threats."
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "extract all significant risks" in user_prompt.lower()

    def test_user_prompt_with_context(self, template):
        """Test context is included in prompt."""
        text = "Sample text"
        context = {
            "document_type": "risk_assessment",
            "industry": "finance",
            "company": "Acme Corp",
            "risk_focus": ["SECURITY", "COMPLIANCE"]
        }
        user_prompt = template.get_user_prompt(text, context)

        assert "risk_assessment" in user_prompt
        assert "finance" in user_prompt
        assert "Acme Corp" in user_prompt
        assert "SECURITY" in user_prompt
        assert "COMPLIANCE" in user_prompt

    def test_user_prompt_without_context(self, template):
        """Test prompt works without context."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text)

        assert text in user_prompt
        assert "## Context" not in user_prompt

    def test_response_model_is_correct(self, template):
        """Test response model is RiskExtractionResult."""
        assert template.response_model == RiskExtractionResult

    def test_template_attributes(self, template):
        """Test template has correct attributes."""
        assert template.name == "risk_extraction"
        assert template.max_tokens == 8192
        assert template.temperature == 0.0

    def test_prompt_registered(self):
        """Test prompt is registered in manager."""
        templates = prompt_manager.list_templates()
        assert "risk_extraction" in templates

        template = prompt_manager.get("risk_extraction")
        assert isinstance(template, RiskExtractionPrompt)

    def test_get_messages(self, template):
        """Test get_messages returns correct structure."""
        text = "Test risk scenario"
        messages = template.get_messages(text)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test risk scenario" in messages[1]["content"]

    def test_truncate_long_text(self, template):
        """Test text truncation."""
        long_text = "Risk: " * 50000
        user_prompt = template.get_user_prompt(long_text)

        assert len(user_prompt) < len(long_text)
        assert "[Text truncated due to length...]" in user_prompt

    def test_system_prompt_guidelines(self, template):
        """Test system prompt includes risk assessment guidelines."""
        system_prompt = template.get_system_prompt()

        assert "severity" in system_prompt.lower()
        assert "likelihood" in system_prompt.lower()
        assert "mitigation" in system_prompt.lower()
        assert "confidence" in system_prompt.lower()

    def test_empty_context(self, template):
        """Test with empty context dict."""
        text = "Sample text"
        user_prompt = template.get_user_prompt(text, {})

        assert text in user_prompt
        assert "## Context" not in user_prompt
