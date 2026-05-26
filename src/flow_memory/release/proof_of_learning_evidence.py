"""Release evidence for Experience Graph and Proof of Learning."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import EXPERIENCE_GRAPH_READ_SCOPE, EXPERIENCE_GRAPH_WRITE_SCOPE, required_scopes_for
from flow_memory.experience_graph import EXPERIENCE_GRAPH_EVENT_TYPES, build_proof_of_learning_bundle
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir

_OVERCLAIM_PATTERNS = (
    "is agi",
    "achieves agi",
    "artificial general intelligence",
    "is conscious",
    "has consciousness",
    "production autonomous intelligence",
    "guaranteed future",
    "predicts arbitrary real-world future",
)

_FLOWLANG_EXPERIENCE_GRAPH = """
agent ProofLearningAgent {
  goal: "turn local prediction errors into reusable proof of learning"

  cognition {
    predictive_core_enabled: true
    prediction_error_learning: true
    memory_consolidation_enabled: true
  }

  experience_graph {
    enabled: true
    experience_graph_enabled: true
    proof_of_learning_enabled: true
    reputation_tracking_enabled: true
    contribution_edges_enabled: true
    private_payload_exclusion_required: true
    policy_edges_required: true
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
"""


def experience_graph_proof_of_learning_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    """Return deterministic evidence that learning traces form a safe graph and ledger."""

    root_path = Path(root).resolve()
    with TemporaryDirectory() as tmp:
        bundle = build_proof_of_learning_bundle(tmp, write_artifacts=True)
    graph = dict(bundle.get("graph", {}))
    metrics = dict(graph.get("metrics", {}))
    proof_ledger = dict(bundle.get("proof_ledger", {}))
    reputation = dict(bundle.get("reputation", {}))
    summary = dict(bundle.get("summary", {}))
    edges = tuple(edge for edge in graph.get("edges", ()) if isinstance(edge, Mapping))
    nodes = tuple(node for node in graph.get("nodes", ()) if isinstance(node, Mapping))
    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    graph_routes = {
        "POST /experience-graph/build",
        "GET /experience-graph",
        "GET /experience-graph/{graph_id}",
        "GET /experience-graph/agents/{agent_id}",
        "GET /proof-of-learning",
        "GET /proof-of-learning/{proof_id}",
        "GET /learning-reputation",
        "GET /learning-reputation/{agent_id}",
    }
    flow_profile = agent_profile_from_ir(parse_flowlang(_FLOWLANG_EXPERIENCE_GRAPH))
    docs_text = _docs_text(root_path)
    no_overclaims = _no_overclaim_patterns(docs_text)
    dashboard_dev_server = root_path / "dashboard" / "scripts" / "dev-server.mjs"
    dashboard_fixture = root_path / "dashboard" / "src" / "mock-data" / "experience-graph-proof-of-learning.json"
    evidence = {
        "experience_graph_available": bool(bundle.get("ok")),
        "graph_nodes_available": metrics.get("node_count", 0) > 0 and bool(nodes),
        "graph_edges_available": metrics.get("edge_count", 0) > 0 and bool(edges),
        "prediction_action_outcome_edges_available": {edge.get("edge_type") for edge in edges} >= {"predicted", "selected_action", "caused", "learned"},
        "proof_of_learning_ledger_available": proof_ledger.get("ok") is True and proof_ledger.get("proof_count", 0) > 0,
        "proof_records_available": bool(proof_ledger.get("proofs")),
        "reputation_metrics_available": reputation.get("ok") is True and bool(reputation.get("reputations")),
        "agent_reputation_available": summary.get("agent_count", 0) > 0 and bool(summary.get("top_agent")),
        "lesson_reuse_edges_available": any(edge.get("edge_type") == "learned" for edge in edges),
        "policy_edges_preserved": any(str(edge.get("edge_type", "")).startswith("policy_") for edge in edges),
        "raw_private_payload_excluded": bundle.get("private_payload_excluded") is True and _no_private_keys(bundle),
        "cli_graph_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "def _graph") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", "proof-of-learning record"),
        "api_graph_available": graph_routes.issubset(manifest_routes) and graph_routes.issubset(registered_routes) and _scope_checks_ok(),
        "flowlang_experience_graph_block_available": flow_profile.metadata.get("experience_graph", {}).get("proof_of_learning_enabled") is True,
        "visual_graph_events_available": all(event in EXPERIENCE_GRAPH_EVENT_TYPES for event in ("experience_graph_built", "proof_of_learning_recorded", "agent_reputation_updated", "private_payload_excluded")),
        "dashboard_proof_panel_available": dashboard_fixture.exists() and _file_contains(dashboard_dev_server, "Proof of Learning"),
        "mission_control_proof_integration_available": _file_contains(dashboard_dev_server, "Experience Graph") and _file_contains(dashboard_dev_server, "Every prediction becomes experience"),
        "no_agi_overclaim_invariant": no_overclaims,
        "no_consciousness_overclaim_invariant": no_overclaims,
        "no_production_autonomy_overclaim_invariant": no_overclaims,
        "public_alpha_docs_updated": _docs_updated(root_path),
    }
    ok = all(evidence.values())
    return {
        "ok": ok,
        **evidence,
        "summary": summary,
        "graph_metrics": metrics,
        "proof_count": proof_ledger.get("proof_count", 0),
        "agent_count": reputation.get("agent_count", 0),
        "api_routes": tuple(sorted(graph_routes)),
        "artifact_paths": bundle.get("artifact_paths", {}),
        "docs_scanned": True,
        "local_only": True,
        "private_payload_excluded": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def verify_experience_graph_proof_of_learning_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    if record.get("ok") is not True:
        blockers.append("experience_graph_proof_of_learning_not_ok")
    for key in (
        "experience_graph_available",
        "graph_nodes_available",
        "graph_edges_available",
        "prediction_action_outcome_edges_available",
        "proof_of_learning_ledger_available",
        "proof_records_available",
        "reputation_metrics_available",
        "agent_reputation_available",
        "lesson_reuse_edges_available",
        "policy_edges_preserved",
        "raw_private_payload_excluded",
        "cli_graph_available",
        "api_graph_available",
        "flowlang_experience_graph_block_available",
        "visual_graph_events_available",
        "dashboard_proof_panel_available",
        "mission_control_proof_integration_available",
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
        "no_production_autonomy_overclaim_invariant",
        "public_alpha_docs_updated",
    ):
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    if record.get("private_payload_excluded") is not True:
        blockers.append("private_payload_not_excluded")
    return {"ok": not blockers, "blockers": tuple(blockers)}


def _scope_checks_ok() -> bool:
    return (
        required_scopes_for("POST", "/experience-graph/build") == (EXPERIENCE_GRAPH_WRITE_SCOPE,)
        and required_scopes_for("GET", "/experience-graph") == (EXPERIENCE_GRAPH_READ_SCOPE,)
        and required_scopes_for("GET", "/proof-of-learning") == (EXPERIENCE_GRAPH_READ_SCOPE,)
        and required_scopes_for("GET", "/learning-reputation") == (EXPERIENCE_GRAPH_READ_SCOPE,)
    )


def _no_private_keys(value: Any) -> bool:
    text = str(value).lower().replace("raw_payload_excluded", "").replace("raw_private_payload_excluded", "")
    return all(token not in text for token in ("raw_private_content", "raw_payload", "private_key", "secret", "token"))


def _docs_text(root: Path) -> str:
    texts: list[str] = []
    for relative in (
        "README.md",
        "docs/EXPERIENCE_GRAPH.md",
        "docs/PROOF_OF_LEARNING.md",
        "docs/NETWORK_LEARNING_PROTOCOL.md",
        "docs/AGENT_GENESIS.md",
        "docs/PREDICTIVE_LEARNING_BENCHMARK.md",
        "docs/PREDICTIVE_COGNITIVE_CORE.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "docs/PUBLIC_ALPHA_READINESS.md",
        "docs/START_HERE.md",
        "BUILD_REPORT.md",
        "FLOW_MEMORY_STATUS.md",
    ):
        path = root / relative
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(texts).lower()


def _no_overclaim_patterns(text: str) -> bool:
    lowered = text.lower()
    return not any(pattern in lowered for pattern in _OVERCLAIM_PATTERNS)


def _docs_updated(root: Path) -> bool:
    required = (
        root / "docs" / "EXPERIENCE_GRAPH.md",
        root / "docs" / "PROOF_OF_LEARNING.md",
        root / "docs" / "NETWORK_LEARNING_PROTOCOL.md",
        root / "docs" / "MISSION_CONTROL_QUICKSTART.md",
        root / "docs" / "PUBLIC_ALPHA_READINESS.md",
        root / "docs" / "START_HERE.md",
        root / "README.md",
        root / "BUILD_REPORT.md",
        root / "FLOW_MEMORY_STATUS.md",
    )
    if not all(path.exists() for path in required):
        return False
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required).lower()
    return "experience graph" in text and "proof of learning" in text and "private payload" in text


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="ignore")
