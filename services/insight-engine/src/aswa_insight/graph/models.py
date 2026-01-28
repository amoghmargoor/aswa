from dataclasses import dataclass, field
from typing import Any, Iterator
from uuid import UUID, uuid4
from enum import Enum
import json

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Types of relationships between entities."""
    WORKS_FOR = "works_for"
    OWNS = "owns"
    PARTNER_OF = "partner_of"
    COMPETITOR_OF = "competitor_of"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    MANAGES = "manages"
    SUPPLIES_TO = "supplies_to"
    ACQUIRES = "acquires"
    INVESTED_IN = "invested_in"
    RELATED_TO = "related_to"


class GraphNode(BaseModel):
    """A node in the entity graph."""
    id: UUID = Field(default_factory=uuid4)
    entity_id: UUID
    name: str
    entity_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    mention_count: int = 1
    document_ids: list[UUID] = Field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, GraphNode):
            return self.id == other.id
        return False


class GraphEdge(BaseModel):
    """An edge (relationship) in the entity graph."""
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    relationship_type: RelationshipType
    description: str | None = None
    confidence: float = 1.0
    bidirectional: bool = False
    weight: float = 1.0
    attributes: dict[str, Any] = Field(default_factory=dict)
    document_ids: list[UUID] = Field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.id)


class EntityGraph(BaseModel):
    """In-memory graph representation of entities and relationships."""
    tenant_id: UUID
    nodes: dict[UUID, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)

    # Adjacency list for efficient traversal
    _adjacency: dict[UUID, list[GraphEdge]] = {}
    _reverse_adjacency: dict[UUID, list[GraphEdge]] = {}

    class Config:
        arbitrary_types_allowed = True

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

        # Update adjacency
        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = []
        self._adjacency[edge.source_id].append(edge)

        # Update reverse adjacency
        if edge.target_id not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target_id] = []
        self._reverse_adjacency[edge.target_id].append(edge)

        # Handle bidirectional
        if edge.bidirectional:
            if edge.target_id not in self._adjacency:
                self._adjacency[edge.target_id] = []
            self._adjacency[edge.target_id].append(edge)

    def get_node(self, node_id: UUID) -> GraphNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: UUID, direction: str = "outgoing") -> list[GraphNode]:
        """Get neighboring nodes.

        Args:
            node_id: Node ID
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of neighboring nodes
        """
        neighbors = []

        if direction in ("outgoing", "both"):
            for edge in self._adjacency.get(node_id, []):
                target = self.nodes.get(edge.target_id)
                if target and target not in neighbors:
                    neighbors.append(target)

        if direction in ("incoming", "both"):
            for edge in self._reverse_adjacency.get(node_id, []):
                source = self.nodes.get(edge.source_id)
                if source and source not in neighbors:
                    neighbors.append(source)

        return neighbors

    def get_edges_for_node(self, node_id: UUID, direction: str = "both") -> list[GraphEdge]:
        """Get edges connected to a node."""
        edges = []

        if direction in ("outgoing", "both"):
            edges.extend(self._adjacency.get(node_id, []))

        if direction in ("incoming", "both"):
            edges.extend(self._reverse_adjacency.get(node_id, []))

        return edges

    def find_path(
        self,
        source_id: UUID,
        target_id: UUID,
        max_depth: int = 5,
    ) -> list[GraphNode] | None:
        """Find shortest path between two nodes (BFS).

        Args:
            source_id: Source node ID
            target_id: Target node ID
            max_depth: Maximum path length

        Returns:
            List of nodes in path, or None if no path exists
        """
        if source_id == target_id:
            node = self.get_node(source_id)
            return [node] if node else None

        visited = {source_id}
        queue = [(source_id, [self.get_node(source_id)])]

        while queue:
            current_id, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            for neighbor in self.get_neighbors(current_id, direction="both"):
                if neighbor.id == target_id:
                    return path + [neighbor]

                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append((neighbor.id, path + [neighbor]))

        return None

    def get_subgraph(
        self,
        center_id: UUID,
        depth: int = 2,
    ) -> "EntityGraph":
        """Get subgraph around a center node.

        Args:
            center_id: Center node ID
            depth: How many hops to include

        Returns:
            New EntityGraph containing the subgraph
        """
        subgraph = EntityGraph(tenant_id=self.tenant_id)

        visited = set()
        queue = [(center_id, 0)]

        while queue:
            node_id, current_depth = queue.pop(0)

            if node_id in visited or current_depth > depth:
                continue

            visited.add(node_id)

            node = self.get_node(node_id)
            if node:
                subgraph.add_node(node)

            if current_depth < depth:
                for neighbor in self.get_neighbors(node_id, direction="both"):
                    if neighbor.id not in visited:
                        queue.append((neighbor.id, current_depth + 1))

        # Add edges between included nodes
        for edge in self.edges:
            if edge.source_id in visited and edge.target_id in visited:
                subgraph.add_edge(edge)

        return subgraph

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": str(self.tenant_id),
            "nodes": [n.model_dump() for n in self.nodes.values()],
            "edges": [e.model_dump() for e in self.edges],
        }
