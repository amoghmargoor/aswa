"""Tests for opportunity extraction models."""

import pytest
from uuid import uuid4

from aswa_insight.models import (
    ExtractedOpportunity,
    OpportunityCategory,
    ImpactLevel,
    EffortLevel,
    ActionItem,
    OpportunityExtractionResult,
    TimeHorizon,
)


class TestExtractedOpportunity:
    """Tests for ExtractedOpportunity model."""

    def test_valid_opportunity_creation(self):
        """Test creating valid opportunity."""
        opportunity = ExtractedOpportunity(
            title="AI Integration",
            description="Integrate AI capabilities into product",
            category=OpportunityCategory.INNOVATION,
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.MEDIUM,
            confidence=0.85,
        )

        assert opportunity.title == "AI Integration"
        assert opportunity.category == OpportunityCategory.INNOVATION
        assert opportunity.impact == ImpactLevel.HIGH
        assert opportunity.effort == EffortLevel.MEDIUM
        assert opportunity.confidence == 0.85
        assert opportunity.prerequisites == []
        assert opportunity.risks == []
        assert opportunity.action_items == []

    def test_opportunity_with_actions(self):
        """Test opportunity with action items."""
        action1 = ActionItem(
            title="Research AI platforms",
            description="Evaluate available AI platforms",
            priority="high",
            estimated_effort=EffortLevel.LOW,
        )

        action2 = ActionItem(
            title="Build prototype",
            description="Create proof of concept",
            priority="medium",
            estimated_effort=EffortLevel.MEDIUM,
            dependencies=["Research AI platforms"],
        )

        opportunity = ExtractedOpportunity(
            title="AI Integration",
            description="Integrate AI capabilities",
            category=OpportunityCategory.TECHNOLOGY,
            impact=ImpactLevel.TRANSFORMATIONAL,
            effort=EffortLevel.HIGH,
            confidence=0.8,
            action_items=[action1, action2],
        )

        assert len(opportunity.action_items) == 2
        assert opportunity.action_items[0].title == "Research AI platforms"
        assert opportunity.action_items[1].priority == "medium"
        assert "Research AI platforms" in opportunity.action_items[1].dependencies

    def test_all_impact_levels(self):
        """Test all impact enum values."""
        impacts = [
            ImpactLevel.TRANSFORMATIONAL,
            ImpactLevel.HIGH,
            ImpactLevel.MEDIUM,
            ImpactLevel.LOW,
        ]

        for impact in impacts:
            opportunity = ExtractedOpportunity(
                title="Test Opportunity",
                description="Test description",
                category=OpportunityCategory.GROWTH,
                impact=impact,
                effort=EffortLevel.MEDIUM,
                confidence=0.8,
            )
            assert opportunity.impact == impact

    def test_all_effort_levels(self):
        """Test all effort level values."""
        efforts = [
            EffortLevel.MINIMAL,
            EffortLevel.LOW,
            EffortLevel.MEDIUM,
            EffortLevel.HIGH,
            EffortLevel.VERY_HIGH,
        ]

        for effort in efforts:
            opportunity = ExtractedOpportunity(
                title="Test Opportunity",
                description="Test description",
                category=OpportunityCategory.EFFICIENCY,
                impact=ImpactLevel.MEDIUM,
                effort=effort,
                confidence=0.8,
            )
            assert opportunity.effort == effort

    def test_opportunity_with_time_to_value(self):
        """Test opportunity with time to value."""
        opportunity = ExtractedOpportunity(
            title="Quick Win",
            description="Fast implementation opportunity",
            category=OpportunityCategory.COST_REDUCTION,
            impact=ImpactLevel.MEDIUM,
            effort=EffortLevel.LOW,
            confidence=0.9,
            time_to_value=TimeHorizon.IMMEDIATE,
        )

        assert opportunity.time_to_value == TimeHorizon.IMMEDIATE

    def test_opportunity_with_full_details(self):
        """Test opportunity with all optional fields."""
        opportunity = ExtractedOpportunity(
            title="Market Expansion",
            description="Expand to new geographic markets",
            category=OpportunityCategory.MARKET_EXPANSION,
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.VERY_HIGH,
            confidence=0.75,
            time_to_value=TimeHorizon.LONG_TERM,
            potential_value="$10M annual revenue",
            prerequisites=["Market research", "Regulatory approval"],
            risks=["High competition", "Regulatory challenges"],
            related_entities=["APAC Region", "Product Team"],
            strategic_alignment="Aligns with 2024 growth strategy",
        )

        assert opportunity.potential_value == "$10M annual revenue"
        assert len(opportunity.prerequisites) == 2
        assert len(opportunity.risks) == 2
        assert opportunity.strategic_alignment == "Aligns with 2024 growth strategy"


class TestActionItem:
    """Tests for ActionItem model."""

    def test_valid_action_item(self):
        """Test creating valid action item."""
        action = ActionItem(
            title="Conduct market research",
            description="Research target market demographics and needs",
            priority="high",
            estimated_effort=EffortLevel.MEDIUM,
        )

        assert action.title == "Conduct market research"
        assert action.priority == "high"
        assert action.estimated_effort == EffortLevel.MEDIUM
        assert action.dependencies == []

    def test_action_with_dependencies(self):
        """Test action item with dependencies."""
        action = ActionItem(
            title="Launch pilot",
            description="Launch pilot program in selected region",
            priority="medium",
            estimated_effort=EffortLevel.HIGH,
            dependencies=["Market research", "Product development"],
        )

        assert len(action.dependencies) == 2
        assert "Market research" in action.dependencies

    def test_all_priority_levels(self):
        """Test all priority values."""
        for priority in ["high", "medium", "low"]:
            action = ActionItem(
                title="Test Action",
                description="Test description",
                priority=priority,
                estimated_effort=EffortLevel.LOW,
            )
            assert action.priority == priority


class TestOpportunityExtractionResult:
    """Tests for OpportunityExtractionResult model."""

    def test_empty_result(self):
        """Test empty opportunity extraction result."""
        result = OpportunityExtractionResult()

        assert result.opportunities == []
        assert result.document_id is None
        assert result.extraction_timestamp is not None

    def test_result_with_opportunities(self):
        """Test result with multiple opportunities."""
        opp1 = ExtractedOpportunity(
            title="Opportunity 1",
            description="First opportunity",
            category=OpportunityCategory.GROWTH,
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.MEDIUM,
            confidence=0.9,
        )

        opp2 = ExtractedOpportunity(
            title="Opportunity 2",
            description="Second opportunity",
            category=OpportunityCategory.EFFICIENCY,
            impact=ImpactLevel.MEDIUM,
            effort=EffortLevel.LOW,
            confidence=0.85,
        )

        doc_id = uuid4()
        result = OpportunityExtractionResult(
            opportunities=[opp1, opp2], document_id=doc_id
        )

        assert len(result.opportunities) == 2
        assert result.document_id == doc_id
        assert result.opportunities[0].title == "Opportunity 1"
