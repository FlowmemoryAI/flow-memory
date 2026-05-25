import json
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import LAUNCH_EXPORT_SCOPE, LAUNCH_READ_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.release.run_console_evidence import mission_control_run_console_evidence
from flow_memory.visualization.run_console import (
    build_public_alpha_demo_bundle,
    event_category_counts,
    get_run_console_run,
    list_run_console_runs,
    run_console_fixtures,
)


def test_run_console_fixtures_and_contracts():
    fixtures = run_console_fixtures()
    assert fixtures["ok"] is True
    ids = {fixture["fixture_id"] for fixture in fixtures["fixtures"]}
    assert {"live-neural-agent-launch", "live-agent-operations", "live-agent-supervisor", "local-network-replay"} <= ids

    console = list_run_console_runs()
    assert console["ok"] is True
    assert console["run_count"] >= 4
    supervisor = get_run_console_run(".", "live-agent-supervisor")
    run = supervisor["run"]
    assert run["run_kind"] == "supervisor"
    assert run["policy_gate_state"]
    assert run["gpu_evidence_status"] in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"}
    assert "neural outputs are advisory" in " ".join(run["warnings"])


def test_event_category_counts_include_supervisor_policy_and_compute():
    counts = event_category_counts(
        (
            {"event_type": "supervisor", "payload": {"event": "live_supervisor_heartbeat"}},
            {"event_type": "safety", "payload": {"event": "neural_policy_gate_applied"}},
            {"event_type": "compute", "payload": {"event": "route_decision_selected"}},
            {"event_type": "memory", "payload": {}},
        )
    )
    assert counts["supervisor"] == 1
    assert counts["policy"] == 1
    assert counts["compute/economy"] == 1
    assert counts["memory"] == 1


def test_public_alpha_demo_bundle_cli_and_shape(tmp_path, capsys):
    out = tmp_path / "public-alpha-local-demo.json"
    assert cli_main(["launch", "bundle", "public-alpha", "--out", str(out), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert out.exists()
    assert payload["ok"] is True
    assert payload["bundle_path"]
    assert payload["gpu_evidence_status"] in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"}
    assert payload["invariants"]["no_external_model_calls"] is True
    assert payload["invariants"]["no_funds_moved"] is True
    assert any("launch supervisor start" in command["command"] for command in payload["commands"])


def test_public_alpha_demo_bundle_helper(tmp_path):
    out = tmp_path / "bundle.json"
    bundle = build_public_alpha_demo_bundle(".", out)
    assert bundle["ok"] is True
    assert out.exists()
    assert bundle["project"]["tagline"] == "The Human Compute Network"
    assert bundle["supervisor_summary"]["run_kind"] == "supervisor"
    assert bundle["invariants"]["neural_advisory_only"] is True
    assert bundle["invariants"]["no_live_settlement"] is True


def test_run_console_api_and_scopes(tmp_path):
    router = create_default_router()
    fixtures = router.dispatch("GET", "/launch/console/fixtures", {})
    assert fixtures["ok"] is True
    assert router.dispatch("GET", "/launch/console/runs", {})["run_count"] >= 4
    assert router.dispatch("GET", "/launch/console/runs/live-agent-supervisor", {})["run"]["run_kind"] == "supervisor"
    bundle = router.dispatch("POST", "/launch/bundles/public-alpha", {"out": str(tmp_path / "api-bundle.json")})
    assert bundle["ok"] is True

    assert required_scopes_for("GET", "/launch/console/runs") == (LAUNCH_READ_SCOPE,)
    assert required_scopes_for("POST", "/launch/bundles/public-alpha") == (LAUNCH_EXPORT_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    read_denied = gateway.handle("GET", "/launch/console/fixtures", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    read_allowed = gateway.handle("GET", "/launch/console/fixtures", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    export_denied = gateway.handle("POST", "/launch/bundles/public-alpha", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"}, json.dumps({"out": str(tmp_path / "denied.json")}).encode())
    export_allowed = gateway.handle("POST", "/launch/bundles/public-alpha", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:export"}, json.dumps({"out": str(tmp_path / "allowed.json")}).encode())
    missing = gateway.handle("GET", "/launch/console/runs/missing-run", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "launch:read"})
    assert read_denied.status == 403
    assert read_allowed.status == 200
    assert export_denied.status == 403
    assert export_allowed.status == 200
    assert missing.status == 404


def test_run_console_release_evidence_ok():
    evidence = mission_control_run_console_evidence()
    assert evidence["ok"] is True
    assert evidence["mission_control_run_console_available"] is True
    assert evidence["mission_control_run_selector_available"] is True
    assert evidence["mission_control_run_status_card_available"] is True
    assert evidence["public_alpha_demo_bundle_cli_available"] is True
    assert evidence["public_alpha_demo_bundle_api_available"] is True
    assert evidence["public_alpha_demo_bundle_validated"] is True
    assert evidence["public_alpha_demo_bundle_gpu_status_honest"] is True
    assert evidence["public_alpha_demo_bundle_no_external_calls"] is True


def test_run_console_docs_include_expected_commands():
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in ("docs/LIVE_AGENT_LAUNCHPAD.md", "docs/MISSION_CONTROL_QUICKSTART.md", "docs/START_HERE.md"))
    assert "python -m flow_memory launch bundle public-alpha" in text
    assert "python -m flow_memory launch supervisor start" in text
    assert "python -m flow_memory launch runs replay" in text
    lowered = text.lower()
    assert "gpu-gated" in lowered
    assert "policy-gated" in lowered or "policy gated" in lowered
    assert "live settlement enabled" not in lowered
    assert "live provider calls enabled" not in lowered
    assert "gpu validated" not in lowered
