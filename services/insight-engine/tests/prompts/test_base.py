"""Tests for base prompt template infrastructure."""

import pytest
from aswa_insight.prompts.base import PromptTemplate, PromptManager
from aswa_insight.models.entities import EntityExtractionResult
from pydantic import BaseModel


class MockPromptTemplate(PromptTemplate):
    """Mock prompt template for testing."""

    name = "mock_template"
    response_model = EntityExtractionResult

    def get_system_prompt(self, context: dict | None = None) -> str:
        if context and context.get("custom_system"):
            return context["custom_system"]
        return "System prompt for mock template"

    def get_user_prompt(self, text: str, context: dict | None = None) -> str:
        if context and context.get("prefix"):
            return f"{context['prefix']}: {text}"
        return f"Analyze: {text}"


class TestPromptTemplate:
    """Test base prompt template functionality."""

    def test_truncate_text_short(self):
        """Test truncation on short text."""
        template = MockPromptTemplate()
        short_text = "This is a short text."
        result = template.truncate_text(short_text, max_chars=1000)
        assert result == short_text
        assert "[Text truncated" not in result

    def test_truncate_text_long(self):
        """Test truncation on long text."""
        template = MockPromptTemplate()
        long_text = "A" * 150000
        result = template.truncate_text(long_text, max_chars=100000)
        assert len(result) < len(long_text)
        assert "[Text truncated due to length...]" in result

    def test_truncate_preserves_sentence(self):
        """Test truncation at sentence boundary."""
        template = MockPromptTemplate()
        # Create text with a sentence ending near 80% of max_chars
        text = "A" * 85000 + ". " + "B" * 15000
        result = template.truncate_text(text, max_chars=100000)
        # Should truncate at the period
        assert result.count('.') >= 1
        assert "[Text truncated due to length...]" in result
        # Should preserve structure by ending at sentence
        assert result.split("[Text truncated")[0].rstrip().endswith(".")

    def test_get_messages_structure(self):
        """Test messages list structure."""
        template = MockPromptTemplate()
        text = "Sample text for analysis"
        messages = template.get_messages(text)

        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt for mock template"
        assert messages[1]["role"] == "user"
        assert "Sample text for analysis" in messages[1]["content"]

    def test_get_messages_with_context(self):
        """Test messages with context."""
        template = MockPromptTemplate()
        text = "Sample text"
        context = {"prefix": "Custom prefix", "custom_system": "Custom system"}
        messages = template.get_messages(text, context)

        assert messages[0]["content"] == "Custom system"
        assert messages[1]["content"] == "Custom prefix: Sample text"

    def test_default_attributes(self):
        """Test default template attributes."""
        template = MockPromptTemplate()
        assert template.max_tokens == 4096
        assert template.temperature == 0.0
        assert template.name == "mock_template"
        assert template.response_model == EntityExtractionResult


class TestPromptManager:
    """Test prompt manager functionality."""

    def test_register_template(self):
        """Test registering a template."""
        manager = PromptManager()
        template = MockPromptTemplate()
        manager.register(template)

        assert "mock_template" in manager.list_templates()

    def test_get_registered_template(self):
        """Test getting registered template."""
        manager = PromptManager()
        template = MockPromptTemplate()
        manager.register(template)

        retrieved = manager.get("mock_template")
        assert retrieved is template
        assert retrieved.name == "mock_template"

    def test_get_unknown_template(self):
        """Test error on unknown template."""
        manager = PromptManager()

        with pytest.raises(ValueError, match="Unknown prompt template: unknown"):
            manager.get("unknown")

    def test_list_templates(self):
        """Test listing templates."""
        manager = PromptManager()

        # Empty manager
        assert manager.list_templates() == []

        # Add templates
        template1 = MockPromptTemplate()
        manager.register(template1)

        templates = manager.list_templates()
        assert len(templates) == 1
        assert "mock_template" in templates

    def test_register_multiple_templates(self):
        """Test registering multiple templates."""
        manager = PromptManager()

        class Template1(PromptTemplate):
            name = "template1"
            response_model = BaseModel

            def get_system_prompt(self, context=None):
                return "System 1"

            def get_user_prompt(self, text, context=None):
                return f"User 1: {text}"

        class Template2(PromptTemplate):
            name = "template2"
            response_model = BaseModel

            def get_system_prompt(self, context=None):
                return "System 2"

            def get_user_prompt(self, text, context=None):
                return f"User 2: {text}"

        t1 = Template1()
        t2 = Template2()

        manager.register(t1)
        manager.register(t2)

        assert len(manager.list_templates()) == 2
        assert manager.get("template1") is t1
        assert manager.get("template2") is t2

    def test_replace_template(self):
        """Test replacing a template with same name."""
        manager = PromptManager()
        template1 = MockPromptTemplate()
        manager.register(template1)

        # Register new template with same name
        template2 = MockPromptTemplate()
        manager.register(template2)

        # Should replace the old one
        assert len(manager.list_templates()) == 1
        assert manager.get("mock_template") is template2
