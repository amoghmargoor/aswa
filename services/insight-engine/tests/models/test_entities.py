"""Tests for entity extraction models."""

import pytest
from uuid import uuid4

from aswa_insight.models import (
    ExtractedEntity,
    EntityType,
    EntityRelationship,
    EntityRelationshipType,
    EntityExtractionResult,
    SourceReference,
    ConfidenceLevel,
)


class TestExtractedEntity:
    """Tests for ExtractedEntity model."""

    def test_valid_entity_creation(self):
        """Test creating valid entity."""
        entity = ExtractedEntity(
            name="OpenAI",
            entity_type=EntityType.ORGANIZATION,
            description="AI research company",
            confidence=0.95,
        )

        assert entity.name == "OpenAI"
        assert entity.entity_type == EntityType.ORGANIZATION
        assert entity.description == "AI research company"
        assert entity.confidence == 0.95
        assert entity.aliases == []
        assert entity.attributes == {}
        assert entity.sources == []

    def test_entity_confidence_bounds(self):
        """Test confidence must be 0-1."""
        # Valid confidence values
        entity = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test entity",
            confidence=0.0,
        )
        assert entity.confidence == 0.0

        entity = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test entity",
            confidence=1.0,
        )
        assert entity.confidence == 1.0

        # Invalid confidence values
        with pytest.raises(Exception):
            ExtractedEntity(
                name="Test",
                entity_type=EntityType.PERSON,
                description="Test entity",
                confidence=1.5,
            )

        with pytest.raises(Exception):
            ExtractedEntity(
                name="Test",
                entity_type=EntityType.PERSON,
                description="Test entity",
                confidence=-0.1,
            )

    def test_entity_type_validation(self):
        """Test entity type enum validation."""
        # Valid entity type
        entity = ExtractedEntity(
            name="Python",
            entity_type=EntityType.TECHNOLOGY,
            description="Programming language",
            confidence=0.9,
        )
        assert entity.entity_type == EntityType.TECHNOLOGY

        # Invalid entity type
        with pytest.raises(Exception):
            ExtractedEntity(
                name="Test",
                entity_type="invalid_type",
                description="Test entity",
                confidence=0.9,
            )

    def test_entity_with_aliases(self):
        """Test entity with multiple aliases."""
        entity = ExtractedEntity(
            name="International Business Machines",
            entity_type=EntityType.ORGANIZATION,
            description="Technology company",
            confidence=0.85,
            aliases=["IBM", "Big Blue"],
        )

        assert len(entity.aliases) == 2
        assert "IBM" in entity.aliases
        assert "Big Blue" in entity.aliases

    def test_entity_serialization(self):
        """Test JSON serialization."""
        entity = ExtractedEntity(
            name="Amazon",
            entity_type=EntityType.ORGANIZATION,
            description="E-commerce company",
            confidence=0.9,
            aliases=["Amazon.com", "AWS"],
            attributes={"industry": "technology", "founded": "1994"},
        )

        data = entity.model_dump()
        assert data["name"] == "Amazon"
        assert data["entity_type"] == "organization"  # use_enum_values=True
        assert data["aliases"] == ["Amazon.com", "AWS"]
        assert data["attributes"]["industry"] == "technology"

    def test_entity_confidence_level_property(self):
        """Test confidence level property."""
        entity_very_low = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test",
            confidence=0.1,
        )
        assert entity_very_low.confidence_level == ConfidenceLevel.VERY_LOW

        entity_low = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test",
            confidence=0.3,
        )
        assert entity_low.confidence_level == ConfidenceLevel.LOW

        entity_medium = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test",
            confidence=0.5,
        )
        assert entity_medium.confidence_level == ConfidenceLevel.MEDIUM

        entity_high = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test",
            confidence=0.7,
        )
        assert entity_high.confidence_level == ConfidenceLevel.HIGH

        entity_very_high = ExtractedEntity(
            name="Test",
            entity_type=EntityType.PERSON,
            description="Test",
            confidence=0.9,
        )
        assert entity_very_high.confidence_level == ConfidenceLevel.VERY_HIGH


class TestEntityRelationship:
    """Tests for EntityRelationship model."""

    def test_valid_relationship(self):
        """Test creating valid relationship."""
        rel = EntityRelationship(
            source_entity="John Doe",
            target_entity="Acme Corp",
            relationship_type=EntityRelationshipType.WORKS_FOR,
            description="John Doe is employed by Acme Corp",
            confidence=0.9,
        )

        assert rel.source_entity == "John Doe"
        assert rel.target_entity == "Acme Corp"
        assert rel.relationship_type == EntityRelationshipType.WORKS_FOR
        assert rel.confidence == 0.9
        assert rel.bidirectional is False

    def test_bidirectional_relationship(self):
        """Test bidirectional flag."""
        rel = EntityRelationship(
            source_entity="Company A",
            target_entity="Company B",
            relationship_type=EntityRelationshipType.PARTNER_OF,
            description="Strategic partnership",
            confidence=0.85,
            bidirectional=True,
        )

        assert rel.bidirectional is True


class TestEntityExtractionResult:
    """Tests for EntityExtractionResult model."""

    def test_empty_result(self):
        """Test empty extraction result."""
        result = EntityExtractionResult()

        assert result.entities == []
        assert result.relationships == []
        assert result.document_id is None
        assert result.extraction_timestamp is not None

    def test_result_with_entities_and_relationships(self):
        """Test full result."""
        entity1 = ExtractedEntity(
            name="Alice Smith",
            entity_type=EntityType.PERSON,
            description="CEO",
            confidence=0.9,
        )

        entity2 = ExtractedEntity(
            name="TechCorp",
            entity_type=EntityType.ORGANIZATION,
            description="Technology company",
            confidence=0.95,
        )

        relationship = EntityRelationship(
            source_entity="Alice Smith",
            target_entity="TechCorp",
            relationship_type=EntityRelationshipType.MANAGES,
            description="Alice is CEO of TechCorp",
            confidence=0.92,
        )

        doc_id = uuid4()
        result = EntityExtractionResult(
            entities=[entity1, entity2],
            relationships=[relationship],
            document_id=doc_id,
        )

        assert len(result.entities) == 2
        assert len(result.relationships) == 1
        assert result.document_id == doc_id
        assert result.entities[0].name == "Alice Smith"
        assert result.relationships[0].relationship_type == EntityRelationshipType.MANAGES
