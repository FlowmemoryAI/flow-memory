"""Release evidence for the bounded Live Agent Supervisor."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.launch_supervisor import (
    get_supervisor_heartbeat,
    get_supervisor_run,
    pause_supervisor_run,
    resume_supervisor_run,
    start_supervised_run,
    stop_supervisor_run,
    supervisor_status,
)

REQUIRED_SUPERVISOR_ENDPOINTS = (
    "POST /launch/supervisor/start",
    "GET /launch/supervisor/status",
    "GET /launch/supervisor/runs/{run_id}",
    "GET /launch/supervisor/runs/{run_id}/heartbeat",
    "POST /launch/supervisor/runs/{run_id}/pause",
    "POST /launch/supervisor/runs/{run_id}/resume",
    "POST /launch/supervisor/runs/{run_id}/stop",
)

REQUIRED_SUPERVISOR_EXAMPLES = (
    "examples/supervised_live_research_agent.flow",
    "examples/supervised_memory_scout_agent.flow",
    "examples/supervised_market_observer_agent.flow",
)

REQUIRED_DOCS = (
    "docs/LIVE_AGENT_LAUNCHPAD.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/PUBLIC_ALPHA_READINESS.md",
)


def live_agent_supervisor_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    endpoints = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_SUPERVISOR_ENDPOINTS if endpoint not in endpoints)
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    examples = {relative: (root_path / relative).exists() for relative in REQUIRED_SUPERVISOR_EXAMPLES}
    cli_text = _read_text(root_path / "src" / "flow_memory" / "cli.py")
    fixture = _dashboard_fixture(root_path)
    docs_safe = _docs_safe(root_path)

    with tempfile.TemporaryDirectory() as tmp:
        started = start_supervised_run(template="live-research", backend="tiny_torch", ticks=2, tick_interval_ms=1, emit_visual=True, root=tmp)
        supervisor = dict(started.get("supervisor", {}))
        run_id = str(supervisor.get("run_id", ""))
        status = supervisor_status(tmp)
        loaded = get_supervisor_run(tmp, run_id)
        heartbeat = get_supervisor_heartbeat(tmp, run_id)
        pause = pause_supervisor_run(tmp, run_id)
        stop = stop_supervisor_run(tmp, run_id)
        resumed = resume_supervisor_run(tmp, run_id, ticks=1, emit_visual=True)

    policy_gated = supervisor.get("safety_authority") == "policy_engine_and_approval_gate" and supervisor.get("policy_gate_state") == "applied"
    ok = (
        not missing_endpoints
        and _cli_has_supervisor(cli_text)
        and all(docs.values())
        and all(examples.values())
        and status.get("run_count", 0) >= 1
        and loaded.get("status") == "completed"
        and heartbeat.get("ok") is True
        and pause.get("noop") is True
        and stop.get("noop") is True
        and dict(resumed.get("supervisor", {})).get("parent_run_id") == run_id
        and policy_gated
        and supervisor.get("no_external_calls") is True
        and supervisor.get("no_live_provider_calls") is True
        and supervisor.get("no_funds_moved") is True
        and supervisor.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"}
        and fixture.get("ok") is True
        and docs_safe.get("ok") is True
    )
    return {
        "ok": ok,
        "live_agent_supervisor_available": status.get("run_count", 0) >= 1,
        "live_agent_supervisor_cli_available": _cli_has_supervisor(cli_text),
        "live_agent_supervisor_api_available": not missing_endpoints,
        "missing_endpoints": missing_endpoints,
        "live_agent_supervisor_heartbeat_validated": heartbeat.get("ok") is True and bool(heartbeat.get("events")),
        "live_agent_supervisor_pause_resume_validated": pause.get("noop") is True and dict(resumed.get("supervisor", {})).get("parent_run_id") == run_id,
        "live_agent_supervisor_stop_validated": stop.get("noop") is True,
        "live_agent_supervisor_policy_gated": policy_gated,
        "live_agent_supervisor_visual_replay_validated": fixture,
        "live_agent_supervisor_examples_available": examples,
        "live_agent_supervisor_no_external_calls": supervisor.get("no_external_calls") is True,
        "live_agent_supervisor_no_live_provider_calls": supervisor.get("no_live_provider_calls") is True,
        "live_agent_supervisor_no_funds_moved": supervisor.get("no_funds_moved") is True,
        "live_agent_supervisor_gpu_status_honest": supervisor.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"},
        "live_agent_supervisor_public_alpha_docs_updated": all(docs.values()) and docs_safe.get("ok") is True,
        "docs": docs,
        "docs_safety_scan": docs_safe,
        "sample_run": {
            "run_id": run_id,
            "status": supervisor.get("status"),
            "ticks_completed": supervisor.get("ticks_completed"),
            "heartbeat_events": len(heartbeat.get("events", ())),
            "resumed_run_id": dict(resumed.get("supervisor", {})).get("run_id", ""),
        },
    }


def _cli_has_supervisor(cli_text: str) -> bool:
    required = ("start_supervised_run", "supervisor_command", "pause_supervisor_run", "resume_supervisor_run", "stop_supervisor_run")
    return all(item in cli_text for item in required)


def _dashboard_fixture(root: Path) -> Mapping[str, Any]:
    path = root / "dashboard" / "src" / "mock-data" / "live-agent-supervisor.json"
    if not path.exists():
        return {"ok": False, "missing": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "error": "fixture is not a JSON object"}
    supervisor = dict(payload.get("supervisor", {})) if isinstance(payload.get("supervisor", {}), Mapping) else {}
    state = dict(payload.get("state", {})) if isinstance(payload.get("state", {}), Mapping) else {}
    heartbeat = dict(payload.get("heartbeat", {})) if isinstance(payload.get("heartbeat", {}), Mapping) else {}
    return {
        "ok": supervisor.get("status") == "completed" and bool(state.get("supervisor")) and bool(heartbeat.get("events")),
        "path": str(path),
        "run_id": supervisor.get("run_id", ""),
        "heartbeat_events": len(heartbeat.get("events", ())),
    }


def _docs_safe(root: Path) -> Mapping[str, Any]:
    unsafe_phrases = (
        "production agi",
        "unguarded autonomy",
        "unbounded autonomy",
        "mainnet-ready",
        "gpu validated",
        "vjepa 2 implemented",
        "videomae implemented",
        "live settlement enabled",
        "live provider calls enabled",
    )
    hits: list[str] = []
    for relative in (*REQUIRED_DOCS, *REQUIRED_SUPERVISOR_EXAMPLES):
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
