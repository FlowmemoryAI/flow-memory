import json
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import LAUNCH_CONTROL_SCOPE, LAUNCH_READ_SCOPE, LAUNCH_RUN_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.flowlang.parser import parse_flowlang_file
from flow_memory.launch_supervisor import (
    get_supervisor_heartbeat,
    get_supervisor_run,
    pause_supervisor_run,
    resume_supervisor_run,
    start_supervised_run,
    stop_supervisor_run,
    supervisor_status,
)
from flow_memory.release.launch_supervisor_evidence import live_agent_supervisor_evidence
from flow_memory.visualization.reducer import reduce_visual_events


def test_supervisor_start_heartbeat_and_registry(tmp_path):
    payload = start_supervised_run(template="live-research", backend="tiny_torch", ticks=2, tick_interval_ms=1, emit_visual=True, root=tmp_path)
    supervisor = payload["supervisor"]
    run_id = supervisor["run_id"]
    assert supervisor["status"] == "completed"
    assert supervisor["ticks_completed"] == 2
    assert supervisor["bounded"] is True
    assert supervisor["safety_authority"] == "policy_engine_and_approval_gate"
    assert payload["run"]["metadata"]["supervised"] is True

    status = supervisor_status(tmp_path)
    assert status["run_count"] == 1
    assert status["latest_run_id"] == run_id
    assert get_supervisor_run(tmp_path, run_id)["supervisor_id"] == supervisor["supervisor_id"]
    heartbeat = get_supervisor_heartbeat(tmp_path, run_id)
    assert heartbeat["ok"] is True
    assert heartbeat["events"][-1]["event"] == "live_supervisor_completed"


def test_supervisor_pause_resume_stop_terminal_noops(tmp_path):
    payload = start_supervised_run(template="memory-scout", ticks=1, tick_interval_ms=1, emit_visual=True, root=tmp_path)
    run_id = payload["supervisor"]["run_id"]
    paused = pause_supervisor_run(tmp_path, run_id)
    stopped = stop_supervisor_run(tmp_path, run_id)
    assert paused["noop"] is True
    assert paused["status_after"] == "completed"
    assert stopped["noop"] is True
    assert stopped["status_after"] == "completed"

    resumed = resume_supervisor_run(tmp_path, run_id, ticks=1, emit_visual=True)
    assert resumed["continued_from_run_id"] == run_id
    assert resumed["supervisor"]["parent_run_id"] == run_id
    assert resumed["supervisor"]["continuation_of"] == run_id
    assert resumed["supervisor"]["status"] == "completed"


def test_cli_supervisor_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli_main(["launch", "supervisor", "start", "--template", "live-research", "--neural", "tiny_torch", "--ticks", "1", "--tick-interval-ms", "1", "--emit-visual", "--json"]) == 0
    started = json.loads(capsys.readouterr().out)
    run_id = started["supervisor"]["run_id"]

    assert cli_main(["launch", "supervisor", "status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["latest_run_id"] == run_id

    assert cli_main(["launch", "supervisor", "show", run_id, "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["supervisor"]["status"] == "completed"

    assert cli_main(["launch", "supervisor", "heartbeat", run_id, "--json"]) == 0
    heartbeat = json.loads(capsys.readouterr().out)
    assert heartbeat["heartbeat"]["events"]

    assert cli_main(["launch", "supervisor", "pause", run_id, "--json"]) == 0
    paused = json.loads(capsys.readouterr().out)
    assert paused["noop"] is True

    assert cli_main(["launch", "supervisor", "resume", run_id, "--ticks", "1", "--emit-visual", "--json"]) == 0
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["continued_from_run_id"] == run_id

    assert cli_main(["launch", "supervisor", "stop", run_id, "--json"]) == 0
    stopped = json.loads(capsys.readouterr().out)
    assert stopped["noop"] is True

    assert cli_main(["launch", "supervisor", "show", "missing-run", "--json"]) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["ok"] is False


def test_api_supervisor_endpoints_and_scopes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = create_default_router()
    started = router.dispatch("POST", "/launch/supervisor/start", {"template": "live-research", "ticks": 1, "tick_interval_ms": 1, "emit_visual": True})
    run_id = started["supervisor"]["run_id"]
    assert router.dispatch("GET", "/launch/supervisor/status", {})["latest_run_id"] == run_id
    assert router.dispatch("GET", f"/launch/supervisor/runs/{run_id}", {})["supervisor"]["status"] == "completed"
    assert router.dispatch("GET", f"/launch/supervisor/runs/{run_id}/heartbeat", {})["heartbeat"]["events"]
    assert router.dispatch("POST", f"/launch/supervisor/runs/{run_id}/pause", {})["noop"] is True
    assert router.dispatch("POST", f"/launch/supervisor/runs/{run_id}/resume", {"ticks": 1})["continued_from_run_id"] == run_id
    assert router.dispatch("POST", f"/launch/supervisor/runs/{run_id}/stop", {})["noop"] is True

    assert required_scopes_for("POST", "/launch/supervisor/start") == (LAUNCH_RUN_SCOPE,)
    assert required_scopes_for("GET", "/launch/supervisor/status") == (LAUNCH_READ_SCOPE,)
    assert required_scopes_for("POST", f"/launch/supervisor/runs/{run_id}/resume") == (LAUNCH_RUN_SCOPE,)
    assert required_scopes_for("POST", f"/launch/supervisor/runs/{run_id}/pause") == (LAUNCH_CONTROL_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/launch/supervisor/status", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/launch/supervisor/status", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    control_denied = gateway.handle("POST", f"/launch/supervisor/runs/{run_id}/pause", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"}, b"{}")
    control_allowed = gateway.handle("POST", f"/launch/supervisor/runs/{run_id}/pause", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:control"}, b"{}")
    missing = gateway.handle("GET", "/launch/supervisor/runs/missing-run", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    assert denied.status == 403
    assert allowed.status == 200
    assert control_denied.status == 403
    assert control_allowed.status == 200
    assert missing.status == 404


def test_supervisor_visual_fixture_reduces():
    payload = json.loads(Path("dashboard/src/mock-data/live-agent-supervisor.json").read_text(encoding="utf-8"))
    state = reduce_visual_events(payload["events"], provenance="replay").as_record()
    assert payload["supervisor"]["status"] == "completed"
    assert payload["heartbeat"]["events"]
    assert state["supervisor"]
    assert state["neural"]
    assert state["safety"]


def test_flowlang_supervisor_examples_parse():
    for path in (
        "examples/supervised_live_research_agent.flow",
        "examples/supervised_memory_scout_agent.flow",
        "examples/supervised_market_observer_agent.flow",
    ):
        spec = parse_flowlang_file(path)
        assert spec.name.startswith("Supervised")
        assert spec.metadata["neural"].get("live_mode") is True


def test_supervisor_release_evidence_ok():
    evidence = live_agent_supervisor_evidence()
    assert evidence["ok"] is True
    assert evidence["live_agent_supervisor_available"] is True
    assert evidence["live_agent_supervisor_cli_available"] is True
    assert evidence["live_agent_supervisor_api_available"] is True
    assert evidence["live_agent_supervisor_heartbeat_validated"] is True
    assert evidence["live_agent_supervisor_pause_resume_validated"] is True
    assert evidence["live_agent_supervisor_policy_gated"] is True
    assert evidence["live_agent_supervisor_no_external_calls"] is True
    assert evidence["live_agent_supervisor_no_funds_moved"] is True
    assert evidence["live_agent_supervisor_gpu_status_honest"] is True


def test_supervisor_docs_do_not_overclaim():
    for path in (
        "docs/LIVE_AGENT_LAUNCHPAD.md",
        "docs/NEURAL_LIVE_AGENTS.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "examples/supervised_live_research_agent.flow",
        "examples/supervised_memory_scout_agent.flow",
        "examples/supervised_market_observer_agent.flow",
    ):
        text = Path(path).read_text(encoding="utf-8").lower()
        assert "production agi" not in text
        assert "unguarded autonomy" not in text
        assert "unbounded autonomy" not in text
        assert "gpu validated" not in text
        assert "vjepa 2 implemented" not in text
        assert "videomae implemented" not in text
