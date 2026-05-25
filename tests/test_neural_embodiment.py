import json
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import LAUNCH_READ_SCOPE, VISUAL_READ_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.release.neural_embodiment_evidence import neural_embodiment_evidence
from flow_memory.visualization.embodiment import build_neural_embodiment_fixture, neural_embodiment_state


def test_neural_embodiment_state_contract_is_visible_and_honest():
    payload = neural_embodiment_state(".", "live-agent-supervisor")
    embodiment = payload["embodiment"]
    graph = payload["graph"]
    assert payload["ok"] is True
    assert embodiment["gpu_evidence_status"] == "verified"
    assert embodiment["neural_advisory_only"] is True
    assert embodiment["policy_authority"] == "policy_engine_and_approval_gate"
    assert embodiment["local_only"] is True
    assert embodiment["no_live_provider_calls"] is True
    assert embodiment["no_funds_moved"] is True
    assert embodiment["memory_activation_count"] > 0
    assert embodiment["learning_tick_count"] > 0
    assert graph["policy_gated"] is True
    assert {node["id"] for node in graph["nodes"]} >= {"agent", "runtime", "perception", "prediction", "memory", "policy", "action", "learning", "supervisor", "gpu"}
    assert any(node["id"] == "gpu" and node["status"] == "verified" for node in graph["nodes"])


def test_neural_embodiment_fixture_generation(tmp_path):
    out = tmp_path / "embodiment.json"
    payload = build_neural_embodiment_fixture(".", "live-agent-supervisor", out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert loaded["fixture_id"] == "live-neural-embodiment"
    assert loaded["embodiment"]["gpu_evidence_status"] == "verified"
    assert loaded["embodiment"]["visual"]["three_ready"] is True


def test_neural_embodiment_cli_export(tmp_path, capsys):
    out = tmp_path / "live-neural-embodiment.json"
    assert cli_main(["launch", "visual", "embodiment", "--run", "live-agent-supervisor", "--out", str(out), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert out.exists()
    assert payload["ok"] is True
    assert payload["fixture_path"]
    assert payload["embodiment"]["gpu_evidence_status"] == "verified"
    assert payload["embodiment"]["policy_gate_state"]


def test_neural_embodiment_api_and_scopes():
    router = create_default_router()
    visual_payload = router.dispatch("GET", "/visual/embodiment/live-agent-supervisor", {})
    launch_payload = router.dispatch("GET", "/launch/console/runs/live-agent-supervisor/embodiment", {})
    assert visual_payload["ok"] is True
    assert launch_payload["ok"] is True
    assert visual_payload["embodiment"]["gpu_evidence_status"] == "verified"
    assert required_scopes_for("GET", "/visual/embodiment/live-agent-supervisor") == (VISUAL_READ_SCOPE,)
    assert required_scopes_for("GET", "/launch/console/runs/live-agent-supervisor/embodiment") == (LAUNCH_READ_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/visual/embodiment/live-agent-supervisor", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    allowed = gateway.handle("GET", "/visual/embodiment/live-agent-supervisor", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "visual:read"})
    assert denied.status == 403
    assert allowed.status == 200


def test_neural_embodiment_release_evidence_ok():
    evidence = neural_embodiment_evidence(".")
    assert evidence["ok"] is True
    assert evidence["neural_embodiment_contract_available"] is True
    assert evidence["neural_embodiment_dashboard_available"] is True
    assert evidence["neural_embodiment_replay_fixture_available"] is True
    assert evidence["neural_embodiment_gpu_status_visible"] is True
    assert evidence["neural_embodiment_policy_gate_visible"] is True
    assert evidence["neural_embodiment_memory_activation_visible"] is True
    assert evidence["neural_embodiment_learning_tick_visible"] is True
    assert evidence["neural_embodiment_no_overclaim_invariant"] is True


def test_neural_embodiment_docs_include_commands_and_limits():
    docs = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "docs/MISSION_CONTROL_QUICKSTART.md",
            "docs/NEURAL_LIVE_AGENTS.md",
            "docs/LIVE_AGENT_LAUNCHPAD.md",
            "docs/PUBLIC_ALPHA_READINESS.md",
            "README.md",
        )
    )
    assert "python -m flow_memory launch visual embodiment" in docs
    assert "/visual/embodiment/" in docs
    lowered = docs.lower()
    assert "neural outputs are advisory" in lowered
    assert "policy" in lowered and "approvalgate" in lowered.lower()
    assert "not agi" in lowered or "not an agi" in lowered
    assert "unbounded autonomous operation" in lowered or "unbounded autonomy" in lowered
    assert "live settlement enabled" not in lowered
    assert "live provider calls enabled" not in lowered
