from dataclasses import dataclass
from typing import Any
from uuid import UUID
import structlog

from .models import EntityGraph, GraphNode, GraphEdge, RelationshipType

logger = structlog.get_logger()


@dataclass
class PathResult:
    """Result of a path query."""
    path: list[GraphNode]
    edges: list[GraphEdge]
    total_weight: float
    hop_count: int


@dataclass
class CentralityResult:
    """Centrality scores for nodes."""
    node_id: UUID
    node_name: str
    degree_centrality: float
    in_degree: int
    out_degree: int


class GraphQueryService:
    """Service for querying entity graphs."""

    def __init__(self, graph: EntityGraph):
        self.graph = graph

    def find_shortest_path(
        self,
        source_name: str,
        target_name: str,
        max_depth: int = 5,
    ) -> PathResult | None:
        """Find shortest path between entities by name.

        Args:
            source_name: Source entity name
            target_name: Target entity name
            max_depth: Maximum path length

        Returns:
            PathResult or None
        """
        source_node = self._find_node_by_name(source_name)
        target_node = self._find_node_by_name(target_name)

        if not source_node or not target_node:
            return None

        path = self.graph.find_path(source_node.id, target_node.id, max_depth)

        if not path:
            return None

        # Collect edges along the path
        edges = []
        for i in range(len(path) - 1):
            edge = self._find_edge(path[i].id, path[i + 1].id)
            if edge:
                edges.append(edge)

        total_weight = sum(e.weight for e in edges)

        return PathResult(
            path=path,
            edges=edges,
            total_weight=total_weight,
            hop_count=len(path) - 1,
        )

    def find_related_entities(
        self,
        entity_name: str,
        relationship_types: list[RelationshipType] | None = None,
        max_depth: int = 2,
    ) -> list[tuple[GraphNode, int]]:
        """Find entities related to the given entity.

        Args:
            entity_name: Entity name
            relationship_types: Optional filter by relationship types
            max_depth: How many hops to traverse

        Returns:
            List of (node, depth) tuples
        """
        start_node = self._find_node_by_name(entity_name)
        if not start_node:
            return []

        results: list[tuple[GraphNode, int]] = []
        visited = {start_node.id}
        queue = [(start_node.id, 0)]

        while queue:
            node_id, depth = queue.pop(0)

            if depth > max_depth:
                continue

            # Get edges from this node
            edges = self.graph.get_edges_for_node(node_id, direction="both")

            for edge in edges:
                # Filter by relationship type if specified
                if relationship_types and edge.relationship_type not in relationship_types:
                    continue

                # Get the other node
                other_id = edge.target_id if edge.source_id == node_id else edge.source_id
                other_node = self.graph.get_node(other_id)

                if other_node and other_id not in visited:
                    visited.add(other_id)
                    results.append((other_node, depth + 1))
                    queue.append((other_id, depth + 1))

        return results

    def find_entities_by_type(
        self,
        entity_type: str,
        min_confidence: float = 0.0,
    ) -> list[GraphNode]:
        """Find all entities of a given type.

        Args:
            entity_type: Entity type to find
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching nodes
        """
        return [
            node for node in self.graph.nodes.values()
            if node.entity_type == entity_type and node.confidence >= min_confidence
        ]

    def find_relationship_chains(
        self,
        relationship_type: RelationshipType,
        min_chain_length: int = 2,
    ) -> list[list[GraphNode]]:
        """Find chains of the same relationship type.

        E.g., A owns B owns C (ownership chain)

        Args:
            relationship_type: Type of relationship
            min_chain_length: Minimum chain length

        Returns:
            List of node chains
        """
        chains = []

        for node in self.graph.nodes.values():
            chain = self._follow_chain(node.id, relationship_type, set())
            if len(chain) >= min_chain_length:
                chains.append(chain)

        return chains

    def calculate_centrality(self) -> list[CentralityResult]:
        """Calculate centrality scores for all nodes.

        Returns:
            List of CentralityResult sorted by centrality
        """
        results = []
        total_nodes = len(self.graph.nodes)

        if total_nodes == 0:
            return []

        for node_id, node in self.graph.nodes.items():
            outgoing = self.graph.get_edges_for_node(node_id, direction="outgoing")
            incoming = self.graph.get_edges_for_node(node_id, direction="incoming")

            in_degree = len(incoming)
            out_degree = len(outgoing)
            degree_centrality = (in_degree + out_degree) / (total_nodes - 1) if total_nodes > 1 else 0

            results.append(CentralityResult(
                node_id=node_id,
                node_name=node.name,
                degree_centrality=degree_centrality,
                in_degree=in_degree,
                out_degree=out_degree,
            ))

        results.sort(key=lambda r: r.degree_centrality, reverse=True)
        return results

    def find_clusters(
        self,
        min_cluster_size: int = 3,
    ) -> list[list[GraphNode]]:
        """Find clusters of connected nodes.

        Args:
            min_cluster_size: Minimum nodes per cluster

        Returns:
            List of node clusters
        """
        visited = set()
        clusters = []

        for node_id in self.graph.nodes:
            if node_id in visited:
                continue

            # BFS to find connected component
            cluster = []
            queue = [node_id]

            while queue:
                current_id = queue.pop(0)
                if current_id in visited:
                    continue

                visited.add(current_id)
                node = self.graph.get_node(current_id)
                if node:
                    cluster.append(node)

                for neighbor in self.graph.get_neighbors(current_id, direction="both"):
                    if neighbor.id not in visited:
                        queue.append(neighbor.id)

            if len(cluster) >= min_cluster_size:
                clusters.append(cluster)

        return clusters

    def _find_node_by_name(self, name: str) -> GraphNode | None:
        """Find node by name (case-insensitive)."""
        name_lower = name.lower()
        for node in self.graph.nodes.values():
            if node.name.lower() == name_lower:
                return node
        return None

    def _find_edge(self, source_id: UUID, target_id: UUID) -> GraphEdge | None:
        """Find edge between two nodes."""
        for edge in self.graph.edges:
            if edge.source_id == source_id and edge.target_id == target_id:
                return edge
            if edge.bidirectional and edge.target_id == source_id and edge.source_id == target_id:
                return edge
        return None

    def _follow_chain(
        self,
        start_id: UUID,
        relationship_type: RelationshipType,
        visited: set[UUID],
    ) -> list[GraphNode]:
        """Follow a chain of same-type relationships."""
        if start_id in visited:
            return []

        visited.add(start_id)
        node = self.graph.get_node(start_id)

        if not node:
            return []

        chain = [node]

        # Find outgoing edges of the same type
        for edge in self.graph.get_edges_for_node(start_id, direction="outgoing"):
            if edge.relationship_type == relationship_type:
                next_chain = self._follow_chain(edge.target_id, relationship_type, visited)
                chain.extend(next_chain)

        return chain
