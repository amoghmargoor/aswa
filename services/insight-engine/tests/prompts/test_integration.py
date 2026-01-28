"""Integration tests for prompts with mock LLM."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aswa_insight.prompts import prompt_manager
from aswa_insight.models.entities import (
    ExtractedEntity,
    EntityRelationship,
    EntityExtractionResult,
)
from aswa_insight.models.risks import ExtractedRisk, RiskExtractionResult
from aswa_insight.models.opportunities import (
    ExtractedOpportunity,
    OpportunityExtractionResult,
)
from aswa_insight.models.patterns import ExtractedPattern, PatternExtractionResult
from aswa_insight.prompts.combined_prompts import CombinedExtractionResult


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.complete_structured = AsyncMock()
    return client


class TestPromptIntegration:
    """Integration tests for prompts with mock LLM."""

    @pytest.mark.asyncio
    async def test_entity_extraction_with_mock_llm(self, mock_llm_client):
        """Test entity prompt produces valid extraction."""
        template = prompt_manager.get("entity_extraction")

        # Setup mock response
        mock_result = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    entity_type="organization",
                    description="Technology company",
                    confidence=0.95,
                )
            ],
            relationships=[],
        )
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages from template
        text = "Apple Inc. announced new products today."
        messages = template.get_messages(text)

        # Verify messages structure
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert text in messages[1]["content"]

        # Simulate LLM call
        result = await mock_llm_client.complete_structured(
            messages=messages,
            response_model=template.response_model,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # Verify result
        assert isinstance(result, EntityExtractionResult)
        assert len(result.entities) == 1
        assert result.entities[0].name == "Apple Inc."
        assert result.entities[0].entity_type == "organization"

    @pytest.mark.asyncio
    async def test_risk_extraction_with_mock_llm(self, mock_llm_client):
        """Test risk prompt produces valid extraction."""
        template = prompt_manager.get("risk_extraction")

        # Setup mock response
        mock_result = RiskExtractionResult(
            risks=[
                ExtractedRisk(
                    title="Cybersecurity Threat",
                    description="Risk of data breach",
                    category="security",
                    severity="high",
                    likelihood="possible",
                    time_horizon="short_term",
                    impact_description="Potential data loss",
                    confidence=0.85,
                )
            ]
        )
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages from template
        text = "The company faces increasing cybersecurity threats."
        messages = template.get_messages(text)

        # Verify messages structure
        assert len(messages) == 2
        assert text in messages[1]["content"]

        # Simulate LLM call
        result = await mock_llm_client.complete_structured(
            messages=messages,
            response_model=template.response_model,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # Verify result
        assert isinstance(result, RiskExtractionResult)
        assert len(result.risks) == 1
        assert result.risks[0].title == "Cybersecurity Threat"
        assert result.risks[0].severity == "high"

    @pytest.mark.asyncio
    async def test_opportunity_extraction_with_mock_llm(self, mock_llm_client):
        """Test opportunity prompt produces valid extraction."""
        template = prompt_manager.get("opportunity_extraction")

        # Setup mock response
        mock_result = OpportunityExtractionResult(
            opportunities=[
                ExtractedOpportunity(
                    title="Market Expansion",
                    description="Expand to Asian markets",
                    category="market_expansion",
                    impact="high",
                    effort="medium",
                    confidence=0.80,
                )
            ]
        )
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages from template
        text = "Strong demand in Asian markets presents expansion opportunity."
        messages = template.get_messages(text)

        # Verify messages structure
        assert len(messages) == 2
        assert text in messages[1]["content"]

        # Simulate LLM call
        result = await mock_llm_client.complete_structured(
            messages=messages,
            response_model=template.response_model,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # Verify result
        assert isinstance(result, OpportunityExtractionResult)
        assert len(result.opportunities) == 1
        assert result.opportunities[0].title == "Market Expansion"
        assert result.opportunities[0].impact == "high"

    @pytest.mark.asyncio
    async def test_pattern_extraction_with_mock_llm(self, mock_llm_client):
        """Test pattern prompt produces valid extraction."""
        template = prompt_manager.get("pattern_extraction")

        # Setup mock response
        mock_result = PatternExtractionResult(
            patterns=[
                ExtractedPattern(
                    title="Revenue Growth",
                    description="15% quarterly revenue increase",
                    pattern_type="trend",
                    direction="increasing",
                    confidence=0.90,
                )
            ]
        )
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages from template
        text = "Revenue increased 15% this quarter, continuing upward trend."
        messages = template.get_messages(text)

        # Verify messages structure
        assert len(messages) == 2
        assert text in messages[1]["content"]

        # Simulate LLM call
        result = await mock_llm_client.complete_structured(
            messages=messages,
            response_model=template.response_model,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # Verify result
        assert isinstance(result, PatternExtractionResult)
        assert len(result.patterns) == 1
        assert result.patterns[0].title == "Revenue Growth"
        assert result.patterns[0].pattern_type == "trend"

    @pytest.mark.asyncio
    async def test_combined_extraction_with_mock_llm(self, mock_llm_client):
        """Test combined prompt produces valid extraction."""
        template = prompt_manager.get("combined_extraction")

        # Setup mock response
        mock_result = CombinedExtractionResult(
            entities=[
                ExtractedEntity(
                    name="TechCorp",
                    entity_type="organization",
                    description="Technology company",
                    confidence=0.95,
                )
            ],
            relationships=[],
            risks=[
                ExtractedRisk(
                    title="Market Competition",
                    description="Increased competition",
                    category="market",
                    severity="medium",
                    likelihood="likely",
                    time_horizon="short_term",
                    impact_description="Market share pressure",
                    confidence=0.80,
                )
            ],
            opportunities=[
                ExtractedOpportunity(
                    title="AI Integration",
                    description="Integrate AI into products",
                    category="innovation",
                    impact="high",
                    effort="medium",
                    confidence=0.85,
                )
            ],
            patterns=[
                ExtractedPattern(
                    title="User Growth",
                    description="20% user growth",
                    pattern_type="trend",
                    direction="increasing",
                    confidence=0.90,
                )
            ],
            summary="TechCorp shows strong growth with AI opportunities and market risks.",
        )
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages from template
        text = "TechCorp reported strong user growth while facing market competition."
        messages = template.get_messages(text)

        # Verify messages structure
        assert len(messages) == 2
        assert text in messages[1]["content"]

        # Simulate LLM call
        result = await mock_llm_client.complete_structured(
            messages=messages,
            response_model=template.response_model,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # Verify result
        assert isinstance(result, CombinedExtractionResult)
        assert len(result.entities) == 1
        assert len(result.risks) == 1
        assert len(result.opportunities) == 1
        assert len(result.patterns) == 1
        assert result.summary is not None
        assert len(result.summary) > 0

    @pytest.mark.asyncio
    async def test_template_with_context(self, mock_llm_client):
        """Test templates work with context."""
        template = prompt_manager.get("entity_extraction")

        # Setup mock response
        mock_result = EntityExtractionResult(entities=[], relationships=[])
        mock_llm_client.complete_structured.return_value = mock_result

        # Get messages with context
        text = "Sample text"
        context = {"document_type": "earnings_report", "industry": "tech"}
        messages = template.get_messages(text, context)

        # Verify context is included
        assert "earnings_report" in messages[1]["content"]
        assert "tech" in messages[1]["content"]

    def test_all_templates_registered(self):
        """Test all expected templates are registered."""
        templates = prompt_manager.list_templates()

        expected = [
            "entity_extraction",
            "risk_extraction",
            "opportunity_extraction",
            "pattern_extraction",
            "combined_extraction",
        ]

        for template_name in expected:
            assert template_name in templates, f"Template {template_name} not registered"

    def test_template_attributes(self):
        """Test all templates have correct attributes."""
        for template_name in prompt_manager.list_templates():
            template = prompt_manager.get(template_name)

            assert hasattr(template, "name")
            assert hasattr(template, "response_model")
            assert hasattr(template, "max_tokens")
            assert hasattr(template, "temperature")
            assert template.max_tokens > 0
            assert 0.0 <= template.temperature <= 1.0
