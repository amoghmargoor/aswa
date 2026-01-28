# Task 3.4.2: Entity Relationship Graph Builder

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The repository layer is implemented at `/services/insight-engine/src/aswa_insight/repository/` with entity and insight storage.

Extracted entities have relationships between them (e.g., "Person works_for Organization"). This task builds a graph structure to represent and query these relationships.

## Objective

Create an entity relationship graph builder that:
1. Builds and maintains a graph of entity relationships
2. Supports graph queries (paths, neighbors, etc.)
3. Integrates with the repository layer
4. Provides visualization-friendly output

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/graph/__init__.py`
```python
from .models import GraphNode, GraphEdge, EntityGraph
from .builder import GraphBuilder
from .queries import GraphQueryService
from .visualization import GraphVisualizer

__all__ = [
    "GraphNode",
    "GraphEdge",
    "EntityGraph",
    "GraphBuilder",
    "GraphQueryService",
    "GraphVisualizer",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/graph/models.py`
Graph data structures:

```python
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
```

### 3. Create `/services/insight-engine/src/aswa_insight/graph/builder.py`
Graph builder from extractions:

```python
from typing import Any
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from aswa_insight.repository.models import EntityModel, InsightModel
from aswa_insight.models.entities import EntityRelationship, ExtractedEntity
from .models import EntityGraph, GraphNode, GraphEdge, RelationshipType

logger = structlog.get_logger()


class GraphBuilder:
    """Build entity relationship graphs from extracted data."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self._entity_cache: dict[str, GraphNode] = {}

    async def build_from_extraction(
        self,
        tenant_id: UUID,
        entities: list[ExtractedEntity],
        relationships: list[EntityRelationship],
        document_id: UUID | None = None,
    ) -> EntityGraph:
        """Build graph from extraction results.

        Args:
            tenant_id: Tenant ID
            entities: Extracted entities
            relationships: Extracted relationships
            document_id: Optional document ID

        Returns:
            EntityGraph
        """
        graph = EntityGraph(tenant_id=tenant_id)

        # Create nodes for entities
        entity_name_to_node: dict[str, GraphNode] = {}

        for entity in entities:
            node = self._create_node(entity, document_id)
            graph.add_node(node)
            entity_name_to_node[entity.name.lower()] = node

        # Create edges for relationships
        for rel in relationships:
            source_node = entity_name_to_node.get(rel.source_entity.lower())
            target_node = entity_name_to_node.get(rel.target_entity.lower())

            if source_node and target_node:
                edge = self._create_edge(rel, source_node.id, target_node.id, document_id)
                graph.add_edge(edge)

        logger.info(
            "Graph built from extraction",
            tenant_id=str(tenant_id),
            nodes=graph.node_count,
            edges=graph.edge_count,
        )

        return graph

    async def build_from_database(
        self,
        tenant_id: UUID,
        document_ids: list[UUID] | None = None,
        entity_types: list[str] | None = None,
    ) -> EntityGraph:
        """Build graph from database entities.

        Args:
            tenant_id: Tenant ID
            document_ids: Optional document filter
            entity_types: Optional entity type filter

        Returns:
            EntityGraph
        """
        if not self.session:
            raise ValueError("Session required for database operations")

        from sqlalchemy import select

        # Query entities
        query = select(EntityModel).where(EntityModel.tenant_id == tenant_id)

        if entity_types:
            query = query.where(EntityModel.entity_type.in_(entity_types))

        result = await self.session.execute(query)
        entities = result.scalars().all()

        graph = EntityGraph(tenant_id=tenant_id)

        # Create nodes
        for entity in entities:
            node = GraphNode(
                entity_id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
                mention_count=entity.mention_count,
                attributes=entity.attributes or {},
            )
            graph.add_node(node)

        # Query and add relationships
        # (Assuming relationships are stored or can be derived)

        return graph

    def merge_graphs(
        self,
        *graphs: EntityGraph,
    ) -> EntityGraph:
        """Merge multiple graphs.

        Args:
            graphs: Graphs to merge

        Returns:
            Merged EntityGraph
        """
        if not graphs:
            raise ValueError("At least one graph required")

        merged = EntityGraph(tenant_id=graphs[0].tenant_id)

        # Track merged nodes by normalized name
        name_to_node: dict[str, GraphNode] = {}

        for graph in graphs:
            for node in graph.nodes.values():
                key = f"{node.name.lower()}:{node.entity_type}"

                if key in name_to_node:
                    # Merge with existing
                    existing = name_to_node[key]
                    existing.confidence = max(existing.confidence, node.confidence)
                    existing.mention_count += node.mention_count
                    existing.document_ids.extend(
                        d for d in node.document_ids if d not in existing.document_ids
                    )
                else:
                    name_to_node[key] = node.model_copy(deep=True)
                    merged.add_node(name_to_node[key])

        # Merge edges
        edge_keys: set[str] = set()

        for graph in graphs:
            for edge in graph.edges:
                # Get merged node IDs
                source_node = graph.get_node(edge.source_id)
                target_node = graph.get_node(edge.target_id)

                if not source_node or not target_node:
                    continue

                source_key = f"{source_node.name.lower()}:{source_node.entity_type}"
                target_key = f"{target_node.name.lower()}:{target_node.entity_type}"

                merged_source = name_to_node.get(source_key)
                merged_target = name_to_node.get(target_key)

                if merged_source and merged_target:
                    edge_key = f"{merged_source.id}:{merged_target.id}:{edge.relationship_type}"

                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        new_edge = edge.model_copy(deep=True)
                        new_edge.source_id = merged_source.id
                        new_edge.target_id = merged_target.id
                        merged.add_edge(new_edge)

        return merged

    def _create_node(
        self,
        entity: ExtractedEntity,
        document_id: UUID | None,
    ) -> GraphNode:
        """Create graph node from entity."""
        return GraphNode(
            entity_id=uuid4(),
            name=entity.name,
            entity_type=entity.entity_type.value,
            confidence=entity.confidence,
            attributes=entity.attributes or {},
            document_ids=[document_id] if document_id else [],
        )

    def _create_edge(
        self,
        relationship: EntityRelationship,
        source_id: UUID,
        target_id: UUID,
        document_id: UUID | None,
    ) -> GraphEdge:
        """Create graph edge from relationship."""
        try:
            rel_type = RelationshipType(relationship.relationship_type.value)
        except ValueError:
            rel_type = RelationshipType.RELATED_TO

        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship_type=rel_type,
            description=relationship.description,
            confidence=relationship.confidence,
            bidirectional=relationship.bidirectional,
            document_ids=[document_id] if document_id else [],
        )


from uuid import uuid4  # Add to imports
```

### 4. Create `/services/insight-engine/src/aswa_insight/graph/queries.py`
Graph query service:

```python
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
```

### 5. Create `/services/insight-engine/src/aswa_insight/graph/visualization.py`
Graph visualization helpers:

```python
from typing import Any
from uuid import UUID
import json

from .models import EntityGraph, GraphNode, GraphEdge


class GraphVisualizer:
    """Generate visualization-friendly graph representations."""

    def __init__(self, graph: EntityGraph):
        self.graph = graph

    def to_d3_json(self) -> dict[str, Any]:
        """Convert to D3.js-compatible format.

        Returns:
            Dict with 'nodes' and 'links' arrays
        """
        nodes = [
            {
                "id": str(node.id),
                "name": node.name,
                "type": node.entity_type,
                "confidence": node.confidence,
                "mentions": node.mention_count,
            }
            for node in self.graph.nodes.values()
        ]

        links = [
            {
                "source": str(edge.source_id),
                "target": str(edge.target_id),
                "type": edge.relationship_type.value,
                "confidence": edge.confidence,
                "bidirectional": edge.bidirectional,
            }
            for edge in self.graph.edges
        ]

        return {"nodes": nodes, "links": links}

    def to_cytoscape_json(self) -> dict[str, Any]:
        """Convert to Cytoscape.js format.

        Returns:
            Dict with 'elements' containing nodes and edges
        """
        elements = []

        for node in self.graph.nodes.values():
            elements.append({
                "data": {
                    "id": str(node.id),
                    "label": node.name,
                    "type": node.entity_type,
                    "confidence": node.confidence,
                },
                "group": "nodes",
            })

        for edge in self.graph.edges:
            elements.append({
                "data": {
                    "id": str(edge.id),
                    "source": str(edge.source_id),
                    "target": str(edge.target_id),
                    "label": edge.relationship_type.value,
                    "confidence": edge.confidence,
                },
                "group": "edges",
            })

        return {"elements": elements}

    def to_graphml(self) -> str:
        """Convert to GraphML format.

        Returns:
            GraphML XML string
        """
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="rel_type" for="edge" attr.name="rel_type" attr.type="string"/>',
            '  <graph id="G" edgedefault="directed">',
        ]

        for node in self.graph.nodes.values():
            lines.append(f'    <node id="{node.id}">')
            lines.append(f'      <data key="name">{self._escape_xml(node.name)}</data>')
            lines.append(f'      <data key="type">{node.entity_type}</data>')
            lines.append('    </node>')

        for edge in self.graph.edges:
            lines.append(f'    <edge id="{edge.id}" source="{edge.source_id}" target="{edge.target_id}">')
            lines.append(f'      <data key="rel_type">{edge.relationship_type.value}</data>')
            lines.append('    </edge>')

        lines.append('  </graph>')
        lines.append('</graphml>')

        return '\n'.join(lines)

    def to_mermaid(self, max_nodes: int = 50) -> str:
        """Convert to Mermaid diagram format.

        Args:
            max_nodes: Maximum nodes to include

        Returns:
            Mermaid diagram string
        """
        lines = ["graph LR"]

        # Limit nodes if too many
        nodes = list(self.graph.nodes.values())[:max_nodes]
        node_ids = {n.id for n in nodes}

        # Create node definitions
        for node in nodes:
            safe_name = self._escape_mermaid(node.name)
            lines.append(f'    {node.id.hex[:8]}["{safe_name}"]')

        # Create edges
        for edge in self.graph.edges:
            if edge.source_id in node_ids and edge.target_id in node_ids:
                rel_label = edge.relationship_type.value.replace("_", " ")
                lines.append(f'    {edge.source_id.hex[:8]} -->|{rel_label}| {edge.target_id.hex[:8]}')

        return '\n'.join(lines)

    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics.

        Returns:
            Statistics dictionary
        """
        entity_types = {}
        for node in self.graph.nodes.values():
            entity_types[node.entity_type] = entity_types.get(node.entity_type, 0) + 1

        relationship_types = {}
        for edge in self.graph.edges:
            key = edge.relationship_type.value
            relationship_types[key] = relationship_types.get(key, 0) + 1

        return {
            "node_count": self.graph.node_count,
            "edge_count": self.graph.edge_count,
            "entity_types": entity_types,
            "relationship_types": relationship_types,
            "avg_degree": (self.graph.edge_count * 2) / max(self.graph.node_count, 1),
        }

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _escape_mermaid(self, text: str) -> str:
        """Escape Mermaid special characters."""
        return text.replace('"', "'").replace("[", "(").replace("]", ")")
```

## Test Requirements

### Create `/services/insight-engine/tests/graph/__init__.py`

### Create `/services/insight-engine/tests/graph/test_models.py`
```python
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
```

### Create `/services/insight-engine/tests/graph/test_builder.py`
```python
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
```

### Create `/services/insight-engine/tests/graph/test_queries.py`
```python
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
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/graph/ -v`
2. Verify imports: `python -c "from aswa_insight.graph import *"`
3. Test visualization output formats
