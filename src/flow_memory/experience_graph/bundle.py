"""High-level Experience Graph + Proof of Learning bundle helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.experience_graph.graph import agent_graph_view, build_experience_graph
from flow_memory.experience_graph.proof import build_proof_ledger, list_proofs
from flow_memory.experience_graph.reputation import compute_reputation, list_reputations, write_reputation_records
from flow_memory.experience_graph.telemetry import proof_graph_to_visual_events


def build_proof_of_learning_bundle(root: str | Path = ".", *, write_artifacts: bool = True) -> Mapping[str, Any]:
    graph_result = build_experience_graph(root, write_artifact=write_artifacts)
    graph = dict(graph_result["graph"])
    proof = build_proof_ledger(graph, root=root, write_artifact=write_artifacts)
    reputation = compute_reputation(tuple(item for item in proof.get("proofs", ()) if isinstance(item, Mapping)), graph)
    if write_artifacts:
        reputation = {**reputation, "write": write_reputation_records(reputation, root=root)}
    events = tuple(event.as_record() for event in proof_graph_to_visual_events({"graph": graph, "proof_ledger": proof, "reputation": reputation}))
    ranked = tuple(reputation.get("reputations", ()))
    return {
        "ok": True,
        "label": "Experience Graph + Proof of Learning",
        "graph": graph,
        "proof_ledger": proof,
        "reputation": reputation,
        "events": events,
        "summary": {
            "headline": "Every prediction becomes experience",
            "graph_loop": "agent → predicted → acted → observed → learned → reused → improved",
            "node_count": graph.get("metrics", {}).get("node_count", 0),
            "edge_count": graph.get("metrics", {}).get("edge_count", 0),
            "proof_count": proof.get("proof_count", 0),
            "agent_count": reputation.get("agent_count", 0),
            "top_agent": ranked[0].get("agent_id", "") if ranked and isinstance(ranked[0], Mapping) else "",
            "raw_private_payload_excluded": True,
            "policy_gates_authoritative": True,
        },
        "agent_view": agent_graph_view(str(ranked[0].get("agent_id", "")) if ranked and isinstance(ranked[0], Mapping) else "network", graph=graph),
        "artifact_paths": {
            "graphs": "artifacts/experience_graph/graphs/",
            "proofs": "artifacts/experience_graph/proofs/",
            "reputation": "artifacts/experience_graph/reputation/",
        },
        "local_only": True,
        "private_payload_excluded": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def write_dashboard_fixture(bundle: Mapping[str, Any], out: str | Path) -> Mapping[str, Any]:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path)}


def current_proof_of_learning_status(root: str | Path = ".") -> Mapping[str, Any]:
    proofs = list_proofs(root)
    reputations = list_reputations(root)
    return {
        "ok": True,
        "proof_count": len(proofs),
        "reputation_count": len(reputations),
        "proofs": proofs,
        "reputations": reputations,
        "local_only": True,
        "private_payload_excluded": True,
    }
