"""One-call build for Experience Graph, Proof of Learning, and reputation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.experience_graph.graph import agent_graph_view, build_experience_graph, latest_graph
from flow_memory.experience_graph.proof import build_proof_ledger, list_proofs
from flow_memory.experience_graph.reputation import compute_reputation, write_reputation_records


def build_learning_ledger(root: str | Path = ".", *, write_artifacts: bool = True) -> Mapping[str, Any]:
    graph_result = build_experience_graph(root, write_artifact=write_artifacts)
    graph = dict(graph_result["graph"])
    proof_ledger = build_proof_ledger(graph, root=root, write_artifact=write_artifacts)
    reputations = compute_reputation(tuple(proof_ledger.get("proofs", ())), graph)
    reputation_write: Mapping[str, Any] = {"ok": True, "count": 0, "paths": ()}
    if write_artifacts:
        reputation_write = write_reputation_records(reputations, root=root)
    metrics = {
        "graph_nodes": graph.get("metrics", {}).get("node_count", 0),
        "graph_edges": graph.get("metrics", {}).get("edge_count", 0),
        "proof_count": proof_ledger.get("proof_count", 0),
        "agent_reputation_count": reputations.get("agent_count", 0),
        "average_proof_score": proof_ledger.get("average_score", 0.0),
        "private_payload_excluded": True,
        "policy_authority": "policy_engine_and_approval_gate",
    }
    return {
        "ok": True,
        "graph": graph,
        "proof_ledger": proof_ledger,
        "reputation": reputations,
        "metrics": metrics,
        "writes": {"graph": graph_result.get("write", {}), "proofs": proof_ledger.get("write", {}), "reputation": reputation_write},
        "local_only": True,
        "raw_private_payload_excluded": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def proof_learning_status(root: str | Path = ".") -> Mapping[str, Any]:
    graph = latest_graph(root)
    proofs = list_proofs(root)
    if not proofs:
        built = build_learning_ledger(root, write_artifacts=True)
        graph = built["graph"]
        proofs = tuple(built["proof_ledger"].get("proofs", ()))
    return {
        "ok": True,
        "graph_id": graph.get("graph_id", ""),
        "metrics": graph.get("metrics", {}),
        "proof_count": len(proofs),
        "proofs": proofs,
        "local_only": True,
        "private_payload_excluded": True,
    }


def agent_learning_view(agent_id: str, root: str | Path = ".") -> Mapping[str, Any]:
    graph_view = agent_graph_view(agent_id, root)
    proofs = tuple(proof for proof in list_proofs(root) if proof.get("agent_id") == agent_id)
    return {"ok": True, "agent_id": agent_id, "graph": graph_view, "proofs": proofs, "proof_count": len(proofs), "private_payload_excluded": True}
