import pytest
from uuid import uuid4

from aswa_insight.graph.builder import GraphBuilder
from aswa_insight.models.entities import ExtractedEntity, EntityRelationship, EntityType, EntityRelationshipType


class TestGraphBuilder:
    @pytest.mark.asyncio
    async def test_build_from_extraction(self):
        """Test building graph from extraction."""
        builder = GraphBuilder()

        entities = [
            ExtractedEntity(name="Acme Corp", entity_type=EntityType.ORGANIZATION, description="A company", confidence=0.9),
            ExtractedEntity(name="John Doe", entity_type=EntityType.PERSON, description="CEO", confidence=0.85),
        ]

        relationships = [
            EntityRelationship(
                source_entity="John Doe",
                target_entity="Acme Corp",
                relationship_type=EntityRelationshipType.WORKS_FOR,
                description="CEO of company",
                confidence=0.8,
            ),
        ]

        graph = await builder.build_from_extraction(
            tenant_id=uuid4(),
            entities=entities,
            relationships=relationships,
        )

        assert graph.node_count == 2
        assert graph.edge_count == 1

    def test_merge_graphs(self):
        """Test merging multiple graphs."""
        builder = GraphBuilder()
        tenant_id = uuid4()

        # Create two graphs with overlapping entities
        # This would require creating graphs first
        pass
