"""Semantic memory: graph of entities, relations, and facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping


@dataclass
class SemanticGraph:
    """Minimal in-memory semantic graph with a Neo4j/Memgraph adapter seam."""

    nodes: MutableMapping[str, Mapping[str, Any]] = field(default_factory=dict)
    edges: list[tuple[str, str, str, Mapping[str, Any]]] = field(default_factory=list)

    def add_node(self, node_id: str, **attrs: Any) -> None:
        existing = dict(self.nodes.get(node_id, {}))
        existing.update(attrs)
        self.nodes[node_id] = existing

    def add_edge(self, source: str, relation: str, target: str, **attrs: Any) -> None:
        self.add_node(source)
        self.add_node(target)
        self.edges.append((source, relation, target, attrs))

    def add_fact(self, subject: str, relation: str, object_: str, **attrs: Any) -> None:
        self.add_edge(subject, relation, object_, **attrs)

    def query(self, term: str) -> tuple[tuple[str, str, str, Mapping[str, Any]], ...]:
        term_lower = term.lower()
        return tuple(
            edge
            for edge in self.edges
            if term_lower in edge[0].lower()
            or term_lower in edge[1].lower()
            or term_lower in edge[2].lower()
        )

    def neighbors(self, node_id: str) -> tuple[tuple[str, str, Mapping[str, Any]], ...]:
        out: list[tuple[str, str, Mapping[str, Any]]] = []
        for source, relation, target, attrs in self.edges:
            if source == node_id:
                out.append((relation, target, attrs))
        return tuple(out)

    def triples(self) -> tuple[tuple[str, str, str], ...]:
        return tuple((source, relation, target) for source, relation, target, _ in self.edges)
