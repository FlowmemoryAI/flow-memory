import json
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import LAUNCH_EXPORT_SCOPE, LAUNCH_READ_SCOPE, LAUNCH_RUN_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.flowlang.parser import parse_flowlang_file
from flow_memory.launch_operations import (
    create_run_record,
    export_run_bundle,
    get_run_record,
    list_run_records,
    load_run_bundle,
    record_run_failure,
    replay_run_record,
    stop_run_record,
    update_run_record,
)
from flow_memory.launchpad import run_live_agent_launch
from flow_memory.release.launch_operations_evidence import live_agent_operations_evidence
from flow_memory.visualization.reducer import reduce_visual_events


def test_run_registry_create_update_list_get_and_failure(tmp_path):
    record = create_run_record(tmp_path, {"run_id": "run-001", "agent_id": "agent", "status": "created", "started_at": "2026-01-01T00:00:00+00:00"})
    assert record["run_record_path"] == "artifacts/launch/runs/run-001.json"
    updated = update_run_record(tmp_path, "run-001", {"status": "running", "tick_count_requested": 3})
    assert updated["status"] == "running"
    assert get_run_record(tmp_path, "run-001")["tick_count_requested"] == 3
    assert [item["run_id"] for item in list_run_records(tmp_path)] == ["run-001"]

    failed = record_run_failure(tmp_path, "run-failed", RuntimeError("safe redacted failure"), {"agent_id": "agent-failed"})
    assert failed["status"] == "failed"
    assert "safe redacted failure" in failed["error_summary"]


def test_launchpad_writes_run_record_and_export_bundle(tmp_path):
    payload = run_live_agent_launch(template="live-research", ticks=2, emit_visual=True, root=tmp_path)
    summary = payload["summary"]
    record = get_run_record(tmp_path, summary["run_id"])
    assert record["status"] == "completed"
    assert record["agent_id"] == summary["agent_id"]
    assert record["replay_artifact_path"] == summary["replay_artifact_path"]
    replay = replay_run_record(tmp_path, summary["run_id"])
    assert replay["ok"] is True
    assert replay["visual_event_count"] == summary["visual_events_emitted"]
    bundle = export_run_bundle(tmp_path, summary["run_id"])
    assert bundle["ok"] is True
    loaded = load_run_bundle(tmp_path / bundle["bundle_path"])
    assert loaded["run_id"] == summary["run_id"]
    stopped = stop_run_record(tmp_path, summary["run_id"])
    assert stopped["noop"] is True
    assert stopped["status_after"] == "completed"


def test_cli_run_operations(tmp_path, monkeypatch, capsys):
    run = run_live_agent_launch(template="live-research", ticks=1, emit_visual=True, root=tmp_path)
    run_id = run["summary"]["run_id"]
    monkeypatch.chdir(tmp_path)

    assert cli_main(["launch", "runs", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["runs"][0]["run_id"] == run_id

    assert cli_main(["launch", "runs", "show", run_id, "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["run"]["status"] == "completed"

    assert cli_main(["launch", "runs", "replay", run_id, "--json"]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["visual_event_count"] >= 8

    assert cli_main(["launch", "runs", "export", run_id, "--json"]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert Path(exported["bundle_path"]).name == f"{run_id}.json"

    assert cli_main(["launch", "runs", "stop", run_id, "--json"]) == 0
    stopped = json.loads(capsys.readouterr().out)
    assert stopped["noop"] is True

    assert cli_main(["launch", "runs", "show", "missing-run", "--json"]) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["ok"] is False
    assert missing["error"]["code"] == "launch.invalid_request"


def test_cli_resume_and_doctor(tmp_path, monkeypatch, capsys):
    run = run_live_agent_launch(template="memory-scout", ticks=1, emit_visual=True, root=tmp_path)
    run_id = run["summary"]["run_id"]
    monkeypatch.chdir(tmp_path)
    assert cli_main(["launch", "runs", "resume", run_id, "--ticks", "1", "--emit-visual", "--json"]) == 0
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["summary"]["continued_from_run_id"] == run_id
    assert resumed["summary"]["loop_ticks_completed"] == 1
    assert cli_main(["launch", "doctor", "--json"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["local_only"] is True
    assert doctor["safety_authority"] == "policy_engine_and_approval_gate"


def test_api_run_operations_and_scopes(tmp_path, monkeypatch):
    run = run_live_agent_launch(template="live-research", ticks=1, emit_visual=True, root=tmp_path)
    run_id = run["summary"]["run_id"]
    monkeypatch.chdir(tmp_path)

    router = create_default_router()
    assert router.dispatch("GET", "/launch/runs", {})["runs"][0]["run_id"] == run_id
    assert router.dispatch("GET", f"/launch/runs/{run_id}", {})["run"]["status"] == "completed"
    assert router.dispatch("POST", f"/launch/runs/{run_id}/replay", {})["visual_event_count"] >= 8
    assert router.dispatch("POST", f"/launch/runs/{run_id}/export", {})["ok"] is True
    assert router.dispatch("POST", f"/launch/runs/{run_id}/stop", {})["noop"] is True

    assert required_scopes_for("GET", "/launch/runs") == (LAUNCH_READ_SCOPE,)
    assert required_scopes_for("POST", f"/launch/runs/{run_id}/replay") == (LAUNCH_READ_SCOPE,)
    assert required_scopes_for("POST", f"/launch/runs/{run_id}/export") == (LAUNCH_EXPORT_SCOPE,)
    assert required_scopes_for("POST", f"/launch/runs/{run_id}/stop") == (LAUNCH_RUN_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/launch/runs", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/launch/runs", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    export_denied = gateway.handle("POST", f"/launch/runs/{run_id}/export", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"}, b"{}")
    export_allowed = gateway.handle("POST", f"/launch/runs/{run_id}/export", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:export"}, b"{}")
    missing = gateway.handle("GET", "/launch/runs/missing-run", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    assert denied.status == 403
    assert allowed.status == 200
    assert export_denied.status == 403
    assert export_allowed.status == 200
    assert missing.status == 404


def test_live_agent_operations_fixture_reduces():
    payload = json.loads(Path("dashboard/src/mock-data/live-agent-operations.json").read_text(encoding="utf-8"))
    state = reduce_visual_events(payload["events"], provenance="replay").as_record()
    assert payload["run_record"]["status"] == "completed"
    assert payload["summary"]["loop_ticks_completed"] == 3
    assert state["agents"]
    assert state["neural"]
    assert state["safety"]
    assert state["memory"]


def test_flowlang_live_ops_examples_parse():
    for path in (
        "examples/live_ops_research_agent.flow",
        "examples/live_ops_memory_scout.flow",
        "examples/live_ops_market_observer.flow",
    ):
        spec = parse_flowlang_file(path)
        assert spec.name.startswith("LiveOps")
        assert spec.metadata["neural"].get("live_mode") is True


def test_live_agent_operations_release_evidence_ok():
    evidence = live_agent_operations_evidence()
    assert evidence["ok"] is True
    assert evidence["live_agent_operations_registry_available"] is True
    assert evidence["live_agent_operations_cli_available"] is True
    assert evidence["live_agent_operations_api_available"] is True
    assert evidence["live_agent_operations_policy_gated"] is True
    assert evidence["live_agent_operations_no_external_calls"] is True
    assert evidence["live_agent_operations_no_funds_moved"] is True
    assert evidence["live_agent_operations_gpu_status_honest"] is True


def test_live_operations_docs_do_not_overclaim():
    for path in (
        "docs/LIVE_AGENT_LAUNCHPAD.md",
        "docs/NEURAL_LIVE_AGENTS.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "examples/live_ops_research_agent.flow",
        "examples/live_ops_memory_scout.flow",
        "examples/live_ops_market_observer.flow",
    ):
        text = Path(path).read_text(encoding="utf-8").lower()
        assert "production agi" not in text
        assert "unguarded autonomy" not in text
        assert "gpu validated" not in text
        assert "vjepa 2 implemented" not in text
        assert "videomae implemented" not in text
