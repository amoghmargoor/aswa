import pytest
from uuid import uuid4

from aswa_insight.graph.models import EntityGraph, GraphNode, GraphEdge, RelationshipType
from aswa_insight.graph.queries import GraphQueryService


class TestGraphQueryService:
    @pytest.fixture
    def sample_graph(self):
        """Create sample graph for testing."""
        graph = EntityGraph(tenant_id=uuid4())

        # Create nodes
        acme = GraphNode(entity_id=uuid4(), name="Acme Corp", entity_type="organization")
        john = GraphNode(entity_id=uuid4(), name="John Doe", entity_type="person")
        jane = GraphNode(entity_id=uuid4(), name="Jane Smith", entity_type="person")

        graph.add_node(acme)
        graph.add_node(john)
        graph.add_node(jane)

        # Create edges
        graph.add_edge(GraphEdge(source_id=john.id, target_id=acme.id, relationship_type=RelationshipType.WORKS_FOR))
        graph.add_edge(GraphEdge(source_id=jane.id, target_id=acme.id, relationship_type=RelationshipType.WORKS_FOR))
        graph.add_edge(GraphEdge(source_id=john.id, target_id=jane.id, relationship_type=RelationshipType.MANAGES))

        return graph

    def test_find_shortest_path(self, sample_graph):
        """Test finding shortest path."""
        query = GraphQueryService(sample_graph)
        result = query.find_shortest_path("John Doe", "Acme Corp")

        assert result is not None
        assert result.hop_count == 1

    def test_find_related_entities(self, sample_graph):
        """Test finding related entities."""
        query = GraphQueryService(sample_graph)
        related = query.find_related_entities("Acme Corp", max_depth=1)

        assert len(related) == 2  # John and Jane

    def test_calculate_centrality(self, sample_graph):
        """Test centrality calculation."""
        query = GraphQueryService(sample_graph)
        centrality = query.calculate_centrality()

        assert len(centrality) == 3
        # Acme should have highest centrality (most connections)

    def test_find_clusters(self, sample_graph):
        """Test cluster finding."""
        query = GraphQueryService(sample_graph)
        clusters = query.find_clusters(min_cluster_size=2)

        assert len(clusters) >= 1
