import pytest
from uuid import uuid4

from aswa_insight.graph.models import EntityGraph, GraphNode, GraphEdge, RelationshipType


class TestGraphNode:
    def test_node_creation(self):
        """Test creating a graph node."""
        node = GraphNode(
            entity_id=uuid4(),
            name="Test Entity",
            entity_type="organization",
        )
        assert node.name == "Test Entity"

    def test_node_hash(self):
        """Test node hashing."""
        node = GraphNode(entity_id=uuid4(), name="Test", entity_type="org")
        assert hash(node) == hash(node.id)


class TestEntityGraph:
    def test_add_node(self):
        """Test adding node to graph."""
        graph = EntityGraph(tenant_id=uuid4())
        node = GraphNode(entity_id=uuid4(), name="Test", entity_type="org")

        graph.add_node(node)
        assert graph.node_count == 1
        assert graph.get_node(node.id) == node

    def test_add_edge(self):
        """Test adding edge to graph."""
        graph = EntityGraph(tenant_id=uuid4())
        node1 = GraphNode(entity_id=uuid4(), name="Node1", entity_type="org")
        node2 = GraphNode(entity_id=uuid4(), name="Node2", entity_type="person")

        graph.add_node(node1)
        graph.add_node(node2)

        edge = GraphEdge(
            source_id=node1.id,
            target_id=node2.id,
            relationship_type=RelationshipType.WORKS_FOR,
        )
        graph.add_edge(edge)

        assert graph.edge_count == 1

    def test_get_neighbors(self):
        """Test getting neighbors."""
        graph = EntityGraph(tenant_id=uuid4())
        node1 = GraphNode(entity_id=uuid4(), name="A", entity_type="org")
        node2 = GraphNode(entity_id=uuid4(), name="B", entity_type="org")

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_edge(GraphEdge(
            source_id=node1.id,
            target_id=node2.id,
            relationship_type=RelationshipType.RELATED_TO,
        ))

        neighbors = graph.get_neighbors(node1.id, direction="outgoing")
        assert len(neighbors) == 1
        assert neighbors[0].name == "B"

    def test_find_path(self):
        """Test path finding."""
        graph = EntityGraph(tenant_id=uuid4())
        nodes = [GraphNode(entity_id=uuid4(), name=f"N{i}", entity_type="org") for i in range(3)]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge(GraphEdge(source_id=nodes[0].id, target_id=nodes[1].id, relationship_type=RelationshipType.RELATED_TO))
        graph.add_edge(GraphEdge(source_id=nodes[1].id, target_id=nodes[2].id, relationship_type=RelationshipType.RELATED_TO))

        path = graph.find_path(nodes[0].id, nodes[2].id)
        assert path is not None
        assert len(path) == 3

    def test_get_subgraph(self):
        """Test subgraph extraction."""
        graph = EntityGraph(tenant_id=uuid4())
        center = GraphNode(entity_id=uuid4(), name="Center", entity_type="org")
        near = GraphNode(entity_id=uuid4(), name="Near", entity_type="org")
        far = GraphNode(entity_id=uuid4(), name="Far", entity_type="org")

        graph.add_node(center)
        graph.add_node(near)
        graph.add_node(far)

        graph.add_edge(GraphEdge(source_id=center.id, target_id=near.id, relationship_type=RelationshipType.RELATED_TO))
        graph.add_edge(GraphEdge(source_id=near.id, target_id=far.id, relationship_type=RelationshipType.RELATED_TO))

        subgraph = graph.get_subgraph(center.id, depth=1)
        assert subgraph.node_count == 2  # center and near
