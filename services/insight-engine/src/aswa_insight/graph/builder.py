from typing import Any
from uuid import UUID, uuid4
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
        entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
        return GraphNode(
            entity_id=uuid4(),
            name=entity.name,
            entity_type=entity_type_str,
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
