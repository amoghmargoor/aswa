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
