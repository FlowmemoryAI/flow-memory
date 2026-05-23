"""ODEI-inspired local constitutional graph memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from flow_memory.memory.memory_policy import CONSTITUTIONAL_DOMAINS, MemoryPolicy, MemoryWriteRequest


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_node_id(domain: str) -> str:
    return f"{domain}_{uuid4().hex}"


@dataclass(frozen=True)
class ConstitutionalNode:
    """A local constitutional memory item scoped to one behavioral domain."""

    domain: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    actor: str = "local-agent"
    source: str = "local"
    confidence: float = 1.0
    node_id: str = field(default_factory=lambda: _new_node_id("memory"))
    created_at: str = field(default_factory=_utc_iso)


@dataclass(frozen=True)
class ConstitutionalEdge:
    """A typed relation between constitutional graph nodes."""

    source: str
    relation: str
    target: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_iso)


@dataclass
class ConstitutionalGraph:
    """In-memory constitutional graph with audited, policy-gated writes.

    Domains are separated first-class indexes rather than tags on one flat list so
    identity, goals, constraints, strategy, tasks, observations, outcomes, and
    reputation can be retrieved independently for local reasoning.
    """

    nodes: dict[str, ConstitutionalNode] = field(default_factory=dict)
    edges: list[ConstitutionalEdge] = field(default_factory=list)
    audit_events: list[Mapping[str, Any]] = field(default_factory=list)
    _by_domain: dict[str, list[str]] = field(
        default_factory=lambda: {domain: [] for domain in CONSTITUTIONAL_DOMAINS}
    )

    def write(
        self,
        domain: str,
        text: str,
        *,
        policy: MemoryPolicy,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "local-agent",
        source: str = "local",
        confidence: float = 1.0,
    ) -> ConstitutionalNode:
        """Write a node only when the supplied policy approves it.

        Every allowed and blocked attempt appends an audit event. Blocked writes
        raise ``PermissionError`` and do not mutate graph nodes or edges.
        """

        normalized_domain = domain.strip().lower()
        request = MemoryWriteRequest(
            domain=normalized_domain,
            text=text,
            metadata=metadata or {},
            actor=actor,
            source=source,
            confidence=confidence,
        )
        decision = policy.evaluate(request)
        if not decision.approved:
            self._audit(
                "memory_write_blocked",
                domain=normalized_domain,
                actor=actor,
                source=source,
                approved=False,
                reasons=tuple(decision.reasons),
                requires_human=decision.requires_human,
                risk_level=decision.risk_level,
            )
            raise PermissionError("memory write blocked: " + ", ".join(decision.reasons))

        node = ConstitutionalNode(
            domain=normalized_domain,
            text=text,
            metadata=metadata or {},
            actor=actor,
            source=source,
            confidence=confidence,
            node_id=_new_node_id(normalized_domain),
        )
        self.nodes[node.node_id] = node
        self._by_domain.setdefault(normalized_domain, []).append(node.node_id)
        self._audit(
            "memory_write_allowed",
            domain=normalized_domain,
            actor=actor,
            source=source,
            approved=True,
            node_id=node.node_id,
            requires_human=decision.requires_human,
            risk_level=decision.risk_level,
        )
        return node

    def relate(
        self,
        source: str,
        relation: str,
        target: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConstitutionalEdge:
        if source not in self.nodes:
            raise KeyError(f"unknown source node: {source}")
        if target not in self.nodes:
            raise KeyError(f"unknown target node: {target}")
        edge = ConstitutionalEdge(
            source=source,
            relation=relation,
            target=target,
            metadata=metadata or {},
        )
        self.edges.append(edge)
        self._audit(
            "memory_edge_added",
            source=source,
            relation=relation,
            target=target,
            approved=True,
        )
        return edge

    def by_domain(self, domain: str) -> tuple[ConstitutionalNode, ...]:
        normalized_domain = domain.strip().lower()
        node_ids = self._by_domain.get(normalized_domain, ())
        return tuple(self.nodes[node_id] for node_id in node_ids)

    def retrieve(
        self,
        domain: str,
        query: str | None = None,
        *,
        limit: int | None = None,
    ) -> tuple[ConstitutionalNode, ...]:
        nodes = self.by_domain(domain)
        if query:
            term = query.lower()
            nodes = tuple(node for node in nodes if term in node.text.lower())
        if limit is not None:
            return nodes[:limit]
        return nodes

    def domains(self) -> tuple[str, ...]:
        return tuple(sorted(CONSTITUTIONAL_DOMAINS))

    def _audit(self, event_type: str, **payload: Any) -> None:
        event = {"event_type": event_type, "timestamp": _utc_iso()}
        event.update(payload)
        self.audit_events.append(event)
