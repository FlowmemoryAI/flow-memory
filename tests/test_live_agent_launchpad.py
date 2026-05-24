import json
import sys

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import AGENT_LAUNCH_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.launchpad import get_launch_template, launch_template_names, launch_templates_manifest, run_live_agent_launch
from flow_memory.release.launchpad_evidence import live_agent_launchpad_evidence
from flow_memory.visualization.reducer import reduce_visual_events


def test_launch_template_registry_serializes():
    assert set(launch_template_names()) == {"live-research", "memory-scout", "market-observer", "mission-control-demo"}
    record = get_launch_template("live-research").as_record()
    assert record["neural"]["backend"] == "tiny_torch"
    assert record["no_external_calls"] is True
    json.dumps(launch_templates_manifest(), default=str)


def test_run_live_agent_launch_writes_summary_and_replay(tmp_path):
    out = tmp_path / "launch.json"
    payload = run_live_agent_launch(template="live-research", backend="tiny_torch", ticks=2, emit_visual=True, artifact_path=out)
    summary = payload["summary"]
    assert out.exists()
    assert summary["loop_ticks_completed"] == 2
    assert summary["perceptions_encoded"] == 2
    assert summary["predictions_generated"] == 2
    assert summary["plans_scored"] == 2
    assert summary["risks_scored"] == 2
    assert summary["learning_steps"] == 2
    assert summary["memory_records_written"] >= 4
    assert summary["visual_events_emitted"] >= 8
    assert summary["no_external_calls"] is True
    assert summary["no_funds_moved"] is True
    assert summary["safety_authority"] == "policy_engine_and_approval_gate"
    assert payload["state"]["neural"]
    assert any(event["event_type"] == "safety" for event in payload["events"])


def test_run_live_agent_launch_from_flow_source(tmp_path):
    source = '''
agent LiveResearchAgent {
  goal: "Explore and report"
  autonomy: "supervised"
  tool: "respond"
  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    seed: 11
    policy_fallback: "allow_non_neural"
  }
}
'''
    payload = run_live_agent_launch(flow_source=source, ticks=1, emit_visual=True, artifact_path=tmp_path / "flow-launch.json")
    assert payload["summary"]["loop_ticks_completed"] == 1
    assert payload["agent"]["neural_config"]["live_mode"] is True
    assert payload["agent"]["neural_config"]["session_id"] == payload["summary"]["session_id"]


def test_cli_launch_command_outputs_json(tmp_path, capsys):
    out = tmp_path / "cli-launch.json"
    rc = cli_main(["launch", "agent", "--template", "live-research", "--neural", "tiny_torch", "--ticks", "1", "--emit-visual", "--out", str(out), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert out.exists()
    assert payload["summary"]["loop_ticks_completed"] == 1
    assert payload["summary"]["backend"] == "tiny_torch"


def test_api_launchpad_endpoint_and_scope_enforcement():
    router = create_default_router()
    direct = router.dispatch("POST", "/launch/agent", {"template": "live-research", "ticks": 1, "emit_visual": True})
    assert direct["summary"]["loop_ticks_completed"] == 1
    assert direct["summary"]["no_external_calls"] is True
    assert required_scopes_for("POST", "/launch/agent") == (AGENT_LAUNCH_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True))
    body = json.dumps({"template": "live-research", "ticks": 1, "emit_visual": True}).encode("utf-8")
    missing = gateway.handle("POST", "/launch/agent", headers={"x-flow-memory-api-key": "dev-local-only"}, body=body)
    allowed = gateway.handle("POST", "/launch/agent", headers={"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "agents:launch"}, body=body)
    assert missing.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["summary"]["loop_ticks_completed"] == 1


def test_launchpad_visual_fixture_reduces():
    payload = json.loads(open("dashboard/src/mock-data/live-neural-agent-launch.json", encoding="utf-8").read())
    state = reduce_visual_events(payload["events"], provenance="replay").as_record()
    assert payload["summary"]["loop_ticks_completed"] == 5
    assert state["agents"]
    assert state["neural"]
    assert state["safety"]


def test_launchpad_release_evidence_ok():
    evidence = live_agent_launchpad_evidence()
    assert evidence["ok"] is True
    assert evidence["launchpad_cli_available"] is True
    assert evidence["launchpad_api_available"] is True
    assert evidence["launch_no_external_calls_invariant"] is True
    assert evidence["launch_no_funds_moved_invariant"] is True
    assert evidence["launch_gpu_status_honest"] is True


def test_examples_do_not_claim_production_gpu():
    for path in (
        "examples/live_research_agent.flow",
        "examples/memory_scout_agent.flow",
        "examples/market_observer_agent.flow",
        "examples/mission_control_demo_agent.flow",
        "docs/LIVE_AGENT_LAUNCHPAD.md",
    ):
        text = open(path, encoding="utf-8").read().lower()
        assert "production agi" not in text
        assert "live settlement" not in text
        assert "vjepa 2 implemented" not in text
        assert "videomae implemented" not in text
