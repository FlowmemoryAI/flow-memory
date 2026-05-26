"""Local API handlers for Experience Graph and Proof of Learning."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.experience_graph import (
    agent_graph_view,
    build_experience_graph,
    build_proof_of_learning_bundle,
    get_graph,
    get_proof,
    get_reputation,
    list_graphs,
    list_proofs,
    list_reputations,
)


def experience_graph_build(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    write_artifacts = bool((payload or {}).get("write_artifacts", True))
    return build_proof_of_learning_bundle(write_artifacts=write_artifacts)


def experience_graph_latest() -> Mapping[str, Any]:
    graphs = list_graphs(".")
    if graphs:
        return {"ok": True, "graph": graphs[-1], "count": len(graphs)}
    return build_experience_graph(".")


def experience_graph_get(graph_id: str) -> Mapping[str, Any]:
    return {"ok": True, "graph": get_graph(graph_id)}


def experience_graph_agent(agent_id: str) -> Mapping[str, Any]:
    return agent_graph_view(agent_id)


def proof_of_learning_records() -> Mapping[str, Any]:
    proofs = list_proofs(".")
    return {"ok": True, "proofs": proofs, "count": len(proofs), "private_payload_excluded": True}


def proof_of_learning_record(proof_id: str) -> Mapping[str, Any]:
    return {"ok": True, "proof": get_proof(proof_id)}


def learning_reputations() -> Mapping[str, Any]:
    records = list_reputations(".")
    return {"ok": True, "reputations": records, "count": len(records), "private_payload_excluded": True}


def learning_reputation(agent_id: str) -> Mapping[str, Any]:
    return {"ok": True, "reputation": get_reputation(agent_id)}
