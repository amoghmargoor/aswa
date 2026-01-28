"""Tests for unified insight model."""

import pytest
from uuid import uuid4

from aswa_insight.models import (
    Insight,
    InsightType,
    ExtractedEntity,
    EntityType,
    ExtractedRisk,
    RiskCategory,
    Severity,
    Likelihood,
    ExtractedOpportunity,
    OpportunityCategory,
    ImpactLevel,
    EffortLevel,
    ExtractedPattern,
    PatternType,
    SourceReference,
)


class TestInsight:
    """Tests for Insight model."""

    def test_insight_from_entity(self):
        """Test creating insight from entity."""
        entity = ExtractedEntity(
            name="Google",
            entity_type=EntityType.ORGANIZATION,
            description="Technology company",
            confidence=0.95,
            aliases=["Alphabet"],
            attributes={"industry": "technology"},
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)

        assert insight.tenant_id == tenant_id
        assert insight.document_id == document_id
        assert insight.insight_type == InsightType.ENTITY
        assert insight.title == "Google"
        assert insight.description == "Technology company"
        assert insight.confidence == 0.95
        assert insight.category == "organization"
        assert insight.severity is None
        assert insight.impact is None
        assert "name" in insight.raw_data
        assert insight.raw_data["name"] == "Google"
        assert insight.raw_data["aliases"] == ["Alphabet"]

    def test_insight_from_risk(self):
        """Test creating insight from risk."""
        risk = ExtractedRisk(
            title="Cybersecurity Risk",
            description="Potential data breach vulnerability",
            category=RiskCategory.SECURITY,
            severity=Severity.HIGH,
            likelihood=Likelihood.LIKELY,
            impact_description="Could expose customer data",
            confidence=0.85,
            affected_areas=["Customer Database", "API"],
            risk_score=75.0,
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_risk(risk, tenant_id, document_id)

        assert insight.tenant_id == tenant_id
        assert insight.document_id == document_id
        assert insight.insight_type == InsightType.RISK
        assert insight.title == "Cybersecurity Risk"
        assert insight.description == "Potential data breach vulnerability"
        assert insight.confidence == 0.85
        assert insight.severity == Severity.HIGH
        assert insight.category == "security"
        assert insight.impact is None
        assert "severity" in insight.raw_data
        assert insight.raw_data["severity"] == "high"
        assert insight.raw_data["likelihood"] == "likely"
        assert insight.raw_data["risk_score"] == 75.0
        assert "Customer Database" in insight.raw_data["affected_areas"]

    def test_insight_from_opportunity(self):
        """Test creating insight from opportunity."""
        opportunity = ExtractedOpportunity(
            title="Cloud Migration",
            description="Migrate infrastructure to cloud",
            category=OpportunityCategory.TECHNOLOGY,
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.MEDIUM,
            confidence=0.8,
            potential_value="30% cost reduction",
            prerequisites=["Security audit", "Budget approval"],
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_opportunity(opportunity, tenant_id, document_id)

        assert insight.tenant_id == tenant_id
        assert insight.document_id == document_id
        assert insight.insight_type == InsightType.OPPORTUNITY
        assert insight.title == "Cloud Migration"
        assert insight.description == "Migrate infrastructure to cloud"
        assert insight.confidence == 0.8
        assert insight.impact == ImpactLevel.HIGH
        assert insight.category == "technology"
        assert insight.severity is None
        assert "impact" in insight.raw_data
        assert insight.raw_data["impact"] == "high"
        assert insight.raw_data["effort"] == "medium"
        assert insight.raw_data["potential_value"] == "30% cost reduction"
        assert "Security audit" in insight.raw_data["prerequisites"]

    def test_insight_from_pattern(self):
        """Test creating insight from pattern."""
        pattern = ExtractedPattern(
            title="Revenue Growth",
            description="Consistent quarterly revenue increase",
            pattern_type=PatternType.TREND,
            confidence=0.92,
            magnitude="15% quarter-over-quarter",
            implications=["Strong market demand", "Scale operations"],
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_pattern(pattern, tenant_id, document_id)

        assert insight.tenant_id == tenant_id
        assert insight.document_id == document_id
        assert insight.insight_type == InsightType.PATTERN
        assert insight.title == "Revenue Growth"
        assert insight.description == "Consistent quarterly revenue increase"
        assert insight.confidence == 0.92
        assert insight.category == "trend"
        assert insight.severity is None
        assert insight.impact is None
        assert "pattern_type" in insight.raw_data
        assert insight.raw_data["pattern_type"] == "trend"
        assert insight.raw_data["magnitude"] == "15% quarter-over-quarter"
        assert "Strong market demand" in insight.raw_data["implications"]

    def test_insight_serialization(self):
        """Test JSON serialization for storage."""
        entity = ExtractedEntity(
            name="Microsoft",
            entity_type=EntityType.ORGANIZATION,
            description="Software company",
            confidence=0.95,
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)

        # Serialize to dict
        data = insight.model_dump()

        assert "id" in data
        assert data["tenant_id"] == str(tenant_id)
        assert data["document_id"] == str(document_id)
        assert data["insight_type"] == "entity"
        assert data["title"] == "Microsoft"
        assert data["confidence"] == 0.95
        assert "raw_data" in data

    def test_insight_with_sources(self):
        """Test insight with source references."""
        source1 = SourceReference(
            text="Google is a technology company",
            page=1,
            section="Introduction",
        )

        source2 = SourceReference(
            text="Founded in 1998",
            page=2,
            start_offset=100,
            end_offset=120,
        )

        entity = ExtractedEntity(
            name="Google",
            entity_type=EntityType.ORGANIZATION,
            description="Technology company",
            confidence=0.95,
            sources=[source1, source2],
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)

        assert len(insight.sources) == 2
        assert insight.sources[0].text == "Google is a technology company"
        assert insight.sources[0].page == 1
        assert insight.sources[1].start_offset == 100

    def test_insight_validation_flags(self):
        """Test user validation flags."""
        entity = ExtractedEntity(
            name="Test",
            entity_type=EntityType.ORGANIZATION,
            description="Test entity",
            confidence=0.9,
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)

        assert insight.user_validated is False
        assert insight.user_feedback is None

        # Update validation
        insight.user_validated = True
        insight.user_feedback = "Confirmed accurate"

        assert insight.user_validated is True
        assert insight.user_feedback == "Confirmed accurate"

    def test_insight_related_entity_ids(self):
        """Test related entity IDs."""
        entity = ExtractedEntity(
            name="Test",
            entity_type=EntityType.ORGANIZATION,
            description="Test entity",
            confidence=0.9,
        )

        tenant_id = uuid4()
        document_id = uuid4()
        related_id1 = uuid4()
        related_id2 = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)
        insight.related_entity_ids = [related_id1, related_id2]

        assert len(insight.related_entity_ids) == 2
        assert related_id1 in insight.related_entity_ids
        assert related_id2 in insight.related_entity_ids

    def test_insight_timestamps(self):
        """Test created_at and updated_at timestamps."""
        entity = ExtractedEntity(
            name="Test",
            entity_type=EntityType.ORGANIZATION,
            description="Test entity",
            confidence=0.9,
        )

        tenant_id = uuid4()
        document_id = uuid4()

        insight = Insight.from_entity(entity, tenant_id, document_id)

        assert insight.created_at is not None
        assert insight.updated_at is not None
        assert insight.created_at == insight.updated_at
