"""Release evidence for Live Agent Operations."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.launch_operations import export_run_bundle, get_run_record, list_run_records, replay_run_record, stop_run_record
from flow_memory.launchpad import run_live_agent_launch

REQUIRED_OPERATION_ENDPOINTS = (
    "GET /launch/runs",
    "GET /launch/runs/{run_id}",
    "POST /launch/runs/{run_id}/replay",
    "POST /launch/runs/{run_id}/export",
    "POST /launch/runs/{run_id}/stop",
)

REQUIRED_OPERATION_EXAMPLES = (
    "examples/live_ops_research_agent.flow",
    "examples/live_ops_memory_scout.flow",
    "examples/live_ops_market_observer.flow",
)

REQUIRED_DOCS = (
    "docs/LIVE_AGENT_LAUNCHPAD.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "docs/MISSION_CONTROL_QUICKSTART.md",
)


def live_agent_operations_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    endpoints = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_OPERATION_ENDPOINTS if endpoint not in endpoints)
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    examples = {relative: (root_path / relative).exists() for relative in REQUIRED_OPERATION_EXAMPLES}
    cli_text = _read_text(root_path / "src" / "flow_memory" / "cli.py")
    fixture = _dashboard_fixture(root_path)
    docs_safe = _docs_safe(root_path)

    with tempfile.TemporaryDirectory() as tmp:
        launch = run_live_agent_launch(template="live-research", backend="tiny_torch", ticks=2, emit_visual=True, root=tmp, write_artifact=True, write_checkpoint=True, write_run_record=True)
        summary = dict(launch.get("summary", {}))
        run_id = str(summary.get("run_id", ""))
        records = list_run_records(tmp)
        record = get_run_record(tmp, run_id)
        replay = replay_run_record(tmp, run_id)
        bundle = export_run_bundle(tmp, run_id)
        stop = stop_run_record(tmp, run_id)

    policy_gated = summary.get("safety_authority") == "policy_engine_and_approval_gate" and summary.get("actions_allowed", 0) + summary.get("actions_denied", 0) == summary.get("loop_ticks_completed")
    ok = (
        not missing_endpoints
        and _cli_has_operations(cli_text)
        and all(docs.values())
        and all(examples.values())
        and bool(records)
        and record.get("status") == "completed"
        and replay.get("ok") is True
        and bundle.get("ok") is True
        and stop.get("noop") is True
        and policy_gated
        and summary.get("no_external_calls") is True
        and summary.get("no_live_provider_calls") is True
        and summary.get("no_funds_moved") is True
        and summary.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"}
        and fixture.get("ok") is True
        and docs_safe.get("ok") is True
    )
    return {
        "ok": ok,
        "live_agent_operations_registry_available": bool(records),
        "live_agent_operations_cli_available": _cli_has_operations(cli_text),
        "live_agent_operations_api_available": not missing_endpoints,
        "missing_endpoints": missing_endpoints,
        "live_agent_operations_replay_available": replay.get("ok") is True,
        "live_agent_operations_export_available": bundle.get("ok") is True,
        "live_agent_operations_examples_available": examples,
        "live_agent_operations_policy_gated": policy_gated,
        "live_agent_operations_no_external_calls": summary.get("no_external_calls") is True,
        "live_agent_operations_no_live_provider_calls": summary.get("no_live_provider_calls") is True,
        "live_agent_operations_no_funds_moved": summary.get("no_funds_moved") is True,
        "live_agent_operations_gpu_status_honest": summary.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"},
        "live_agent_operations_dashboard_fixture_valid": fixture,
        "docs": docs,
        "docs_safety_scan": docs_safe,
        "sample_run": {
            "run_id": run_id,
            "record_status": record.get("status"),
            "replay_artifact_path": record.get("replay_artifact_path"),
            "bundle_ok": bundle.get("ok"),
            "stop_noop": stop.get("noop"),
            "summary": summary,
        },
    }


def _cli_has_operations(cli_text: str) -> bool:
    required = ("run_command", "export_run_bundle", "replay_run_record", "stop_run_record", "_launch_doctor")
    return all(item in cli_text for item in required)


def _dashboard_fixture(root: Path) -> Mapping[str, Any]:
    path = root / "dashboard" / "src" / "mock-data" / "live-agent-operations.json"
    if not path.exists():
        return {"ok": False, "missing": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "error": "fixture is not a JSON object"}
    summary = dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {}
    state = dict(payload.get("state", {})) if isinstance(payload.get("state", {}), Mapping) else {}
    run_record = dict(payload.get("run_record", {})) if isinstance(payload.get("run_record", {}), Mapping) else {}
    return {
        "ok": summary.get("loop_ticks_completed", 0) >= 2 and bool(state.get("neural")) and run_record.get("status") == "completed",
        "path": str(path),
        "run_id": summary.get("run_id", ""),
        "visual_events": summary.get("visual_events_emitted", 0),
    }


def _docs_safe(root: Path) -> Mapping[str, Any]:
    unsafe_phrases = (
        "production agi",
        "unguarded autonomy",
        "live settlement",
        "live provider calls",
        "mainnet-ready",
        "gpu validated",
        "vjepa 2 implemented",
        "videomae implemented",
    )
    hits: list[str] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in unsafe_phrases:
            if phrase in text:
                hits.append(f"{relative}:{phrase}")
    return {"ok": not hits, "hits": tuple(hits)}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")
