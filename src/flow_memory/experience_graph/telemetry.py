"""Mission Control visual telemetry for Proof of Learning."""
from __future__ import annotations

from typing import Mapping

from flow_memory.visualization.events import VisualEvent, visual_event

EXPERIENCE_GRAPH_EVENT_TYPES = (
    "experience_graph_built",
    "experience_graph_node_recorded",
    "experience_graph_edge_recorded",
    "proof_of_learning_recorded",
    "agent_reputation_updated",
    "lesson_reuse_linked",
    "policy_denial_preserved",
    "private_payload_excluded",
)


def proof_graph_to_visual_events(bundle: Mapping[str, object], *, provenance: str = "replay") -> tuple[VisualEvent, ...]:
    graph = dict(bundle.get("graph", {})) if isinstance(bundle.get("graph"), Mapping) else {}
    proof = dict(bundle.get("proof_ledger", {})) if isinstance(bundle.get("proof_ledger"), Mapping) else {}
    reputation = dict(bundle.get("reputation", {})) if isinstance(bundle.get("reputation"), Mapping) else {}
    graph_id = str(graph.get("graph_id", "experience_graph"))
    events = []
    for event_type in EXPERIENCE_GRAPH_EVENT_TYPES:
        events.append(visual_event("proof_of_learning", graph_id, _payload(event_type, graph, proof, reputation), provenance=provenance))
    return tuple(events)


def _payload(event_type: str, graph: Mapping[str, object], proof: Mapping[str, object], reputation: Mapping[str, object]) -> Mapping[str, object]:
    metrics = dict(graph.get("metrics", {})) if isinstance(graph.get("metrics"), Mapping) else {}
    return {
        "event": event_type,
        "graph_id": graph.get("graph_id", ""),
        "node_count": metrics.get("node_count", 0),
        "edge_count": metrics.get("edge_count", 0),
        "proof_count": proof.get("proof_count", 0),
        "agent_count": reputation.get("agent_count", 0),
        "policy_override_rate": metrics.get("policy_override_rate", 0.0),
        "raw_private_payload_excluded": graph.get("raw_private_payload_excluded", True),
        "safety_authority": graph.get("safety_authority", "policy_engine_and_approval_gate"),
    }
