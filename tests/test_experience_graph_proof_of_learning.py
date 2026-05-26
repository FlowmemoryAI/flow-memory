import json
import subprocess
import sys

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import EXPERIENCE_GRAPH_READ_SCOPE, EXPERIENCE_GRAPH_WRITE_SCOPE, required_scopes_for
from flow_memory.experience_graph import build_experience_graph, build_proof_of_learning_bundle
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.release.proof_of_learning_evidence import (
    experience_graph_proof_of_learning_evidence,
    verify_experience_graph_proof_of_learning_evidence,
)
from flow_memory.release.readiness import decide_release_readiness


FLOWLANG_GRAPH = '''
agent ProofLearningAgent {
  experience_graph {
    enabled: true
    proof_of_learning_enabled: true
    reputation_tracking_enabled: true
    private_payload_exclusion_required: true
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
'''


def test_experience_graph_builds_demo_nodes_edges_and_sanitizes_private_fields(tmp_path):
    result = build_experience_graph(tmp_path, write_artifact=True)
    graph = result["graph"]
    node_types = {node["node_type"] for node in graph["nodes"]}
    edge_types = {edge["edge_type"] for edge in graph["edges"]}
    text = json.dumps(graph, sort_keys=True)

    assert result["ok"] is True
    assert {"agent", "prediction", "action", "outcome", "prediction_error", "lesson", "policy"}.issubset(node_types)
    assert {"predicted", "selected_action", "caused", "failed_because", "learned", "policy_applied"}.issubset(edge_types)
    assert graph["metrics"]["node_count"] >= 7
    assert "raw_private_content" not in text
    assert "token" not in text


def test_proof_bundle_contains_proofs_reputation_and_visual_events(tmp_path):
    bundle = build_proof_of_learning_bundle(tmp_path, write_artifacts=True)

    assert bundle["ok"] is True
    assert bundle["proof_ledger"]["proof_count"] >= 1
    assert bundle["reputation"]["agent_count"] >= 1
    assert bundle["summary"]["headline"] == "Every prediction becomes experience"
    assert bundle["summary"]["policy_gates_authoritative"] is True
    assert bundle["private_payload_excluded"] is True
    assert any(event["payload"]["event"] == "proof_of_learning_recorded" for event in bundle["events"])


def test_graph_cli_build_and_reputation_list_return_json():
    build = subprocess.run(
        [sys.executable, "-m", "flow_memory", "graph", "build", "--no-write", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(build.stdout)

    assert payload["ok"] is True
    assert payload["summary"]["proof_count"] >= 1


def test_experience_graph_api_routes_and_scopes_are_enforced():
    router = create_default_router()
    built = router.dispatch("POST", "/experience-graph/build", {"write_artifacts": False})
    graph = router.dispatch("GET", "/experience-graph")
    proofs = router.dispatch("GET", "/proof-of-learning")

    assert built["ok"] is True
    assert graph["ok"] is True
    assert proofs["ok"] is True
    assert required_scopes_for("GET", "/experience-graph") == (EXPERIENCE_GRAPH_READ_SCOPE,)
    assert required_scopes_for("GET", "/proof-of-learning") == (EXPERIENCE_GRAPH_READ_SCOPE,)
    assert required_scopes_for("POST", "/experience-graph/build") == (EXPERIENCE_GRAPH_WRITE_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("POST", "/experience-graph/build", {"x-flow-memory-scopes": EXPERIENCE_GRAPH_READ_SCOPE}, b"{}")
    allowed = gateway.handle("GET", "/proof-of-learning", {"x-flow-memory-scopes": EXPERIENCE_GRAPH_READ_SCOPE}, b"")

    assert denied.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["private_payload_excluded"] is True


def test_flowlang_experience_graph_block_converts_to_agent_profile():
    profile = agent_profile_from_ir(parse_flowlang(FLOWLANG_GRAPH))

    assert profile.metadata["experience_graph"]["proof_of_learning_enabled"] is True
    assert profile.metadata["experience_graph"]["reputation_tracking_enabled"] is True


def test_mission_control_proof_fixture_is_valid():
    with open("dashboard/src/mock-data/experience-graph-proof-of-learning.json", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["ok"] is True
    assert payload["label"] == "Experience Graph + Proof of Learning"
    assert payload["summary"]["headline"] == "Every prediction becomes experience"
    assert payload["proof_ledger"]["proof_count"] >= 1
    assert payload["private_payload_excluded"] is True


def test_experience_graph_release_evidence_fields():
    evidence = experience_graph_proof_of_learning_evidence(".")
    decision = verify_experience_graph_proof_of_learning_evidence(evidence)

    assert evidence["experience_graph_available"] is True
    assert evidence["proof_of_learning_ledger_available"] is True
    assert evidence["reputation_metrics_available"] is True
    assert evidence["raw_private_payload_excluded"] is True
    assert evidence["api_graph_available"] is True
    assert evidence["dashboard_proof_panel_available"] is True
    assert decision["ok"] is True


def test_release_decision_public_alpha_proof_of_learning_target_is_known():
    decision = decide_release_readiness(".", target="public-alpha-proof-of-learning")

    assert decision.target == "public-alpha-proof-of-learning"
    assert "experience_graph_proof_of_learning" in decision.required_evidence
