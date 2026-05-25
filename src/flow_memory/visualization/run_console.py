"""Mission Control run console data contract and public-alpha demo bundle helpers.

The run console is a local, read-only projection over Flow Memory launchpad,
operations, supervisor, and replay artifacts. It never starts background work,
never contacts external providers, and never treats GPU evidence as present unless
local evidence artifacts exist.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from flow_memory.launch_operations import get_run_record, list_run_records
from flow_memory.launch_supervisor import get_supervisor_run, supervisor_status

RUN_CONSOLE_VERSION = "flow-memory-mission-control-run-console-v1"
PUBLIC_ALPHA_DEMO_BUNDLE_VERSION = "flow-memory-public-alpha-local-demo-bundle-v1"

FIXTURE_SPECS: tuple[Mapping[str, str], ...] = (
    {
        "fixture_id": "live-neural-agent-launch",
        "label": "Live Neural Agent Launch",
        "description": "One-shot local neural-live agent launch replay.",
        "path": "dashboard/src/mock-data/live-neural-agent-launch.json",
        "run_kind": "launchpad",
    },
    {
        "fixture_id": "live-agent-operations",
        "label": "Live Agent Operations",
        "description": "Run registry, replay, export, and stop/resume local operations replay.",
        "path": "dashboard/src/mock-data/live-agent-operations.json",
        "run_kind": "operations",
    },
    {
        "fixture_id": "live-agent-supervisor",
        "label": "Live Agent Supervisor",
        "description": "Bounded supervisor heartbeat, tick, pause/resume/stop replay.",
        "path": "dashboard/src/mock-data/live-agent-supervisor.json",
        "run_kind": "supervisor",
    },
    {
        "fixture_id": "local-network-replay",
        "label": "Local Network Replay",
        "description": "Local requester/worker/verifier/auditor network replay.",
        "path": "dashboard/src/mock-data/local-network-replay.json",
        "run_kind": "local_network",
    },
    {
        "fixture_id": "live-neural-embodiment",
        "label": "Live Neural Embodiment",
        "description": "3D-ready neural runtime/session, loop phase, policy gate, memory, learning, heartbeat, and GPU evidence replay.",
        "path": "dashboard/src/mock-data/live-neural-embodiment.json",
        "run_kind": "embodiment",
    },
)

CATEGORY_ALIASES: Mapping[str, str] = {
    "agent": "action",
    "task": "action",
    "memory": "memory",
    "economy": "compute/economy",
    "compute": "compute/economy",
    "neural": "neural",
    "rl": "action",
    "safety": "audit/safety",
    "audit": "audit/safety",
    "supervisor": "supervisor",
}


def run_console_fixtures(root: str | Path = ".") -> Mapping[str, Any]:
    """Return dashboard replay fixtures with compact run summaries."""

    root_path = Path(root).resolve()
    fixtures = []
    for spec in FIXTURE_SPECS:
        path = root_path / str(spec["path"])
        payload = _read_json(path)
        summary = _summary_from_fixture_payload(root_path, spec, payload)
        fixtures.append(
            {
                **dict(spec),
                "ok": bool(summary.get("ok")),
                "exists": path.exists(),
                "summary": summary,
                "event_category_counts": event_category_counts(_events_from_payload(payload)),
            }
        )
    return {"ok": all(item["ok"] for item in fixtures), "schema_version": RUN_CONSOLE_VERSION, "fixtures": tuple(fixtures)}


def list_run_console_runs(root: str | Path = ".") -> Mapping[str, Any]:
    """List local run records and replay fixtures for Mission Control."""

    root_path = Path(root).resolve()
    run_summaries = [summarize_run_record(root_path, record) for record in list_run_records(root_path)]
    supervisor_summaries = [
        summarize_supervisor_record(root_path, record)
        for record in dict(supervisor_status(root_path)).get("runs", ())
        if isinstance(record, Mapping)
    ]
    fixture_summaries = [dict(item["summary"]) for item in dict(run_console_fixtures(root_path)).get("fixtures", ())]
    all_runs = tuple(run_summaries + supervisor_summaries + fixture_summaries)
    return {
        "ok": True,
        "schema_version": RUN_CONSOLE_VERSION,
        "runs": all_runs,
        "run_count": len(all_runs),
        "fixtures": tuple(dict(item) for item in dict(run_console_fixtures(root_path)).get("fixtures", ())),
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def get_run_console_run(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Return a single console run summary by run id or fixture id."""

    root_path = Path(root).resolve()
    for record in list_run_records(root_path):
        if str(record.get("run_id", "")) == run_id:
            return {"ok": True, "run": summarize_run_record(root_path, record), "source": "run_record"}
    try:
        supervisor = get_supervisor_run(root_path, run_id)
    except KeyError:
        supervisor = {}
    if supervisor:
        return {"ok": True, "run": summarize_supervisor_record(root_path, supervisor), "source": "supervisor_state"}
    fixtures = run_console_fixtures(root_path)
    for fixture in fixtures.get("fixtures", ()):  # type: ignore[union-attr]
        if not isinstance(fixture, Mapping):
            continue
        summary = dict(fixture.get("summary", {})) if isinstance(fixture.get("summary", {}), Mapping) else {}
        if run_id in {str(fixture.get("fixture_id", "")), str(summary.get("run_id", ""))}:
            return {"ok": True, "run": summary, "fixture": fixture, "source": "fixture"}
    raise KeyError(f"Unknown Mission Control run: {run_id}")


def summarize_run_record(root: str | Path, record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Normalize a launch/operations run record into the dashboard contract."""

    root_path = Path(root).resolve()
    metadata = dict(record.get("metadata", {})) if isinstance(record.get("metadata", {}), Mapping) else {}
    replay = _read_json(_resolve(root_path, str(record.get("replay_artifact_path", ""))))
    events = _events_from_payload(replay)
    summary = dict(replay.get("summary", {})) if isinstance(replay.get("summary", {}), Mapping) else {}
    state = dict(replay.get("state", {})) if isinstance(replay.get("state", {}), Mapping) else {}
    run_kind = "supervisor" if metadata.get("supervised") is True else "operations"
    if str(record.get("template", "")) and not metadata.get("supervised"):
        run_kind = "launchpad"
    return _run_contract(
        root_path,
        run_id=str(record.get("run_id", "")),
        run_kind=run_kind,
        agent_id=str(record.get("agent_id", summary.get("agent_id", ""))),
        session_id=str(record.get("session_id", summary.get("session_id", ""))),
        supervisor_id=str(metadata.get("supervisor_id", "")),
        template=str(record.get("template", summary.get("template", ""))),
        flow_source=str(record.get("flow_source", "")),
        backend=str(record.get("backend", summary.get("backend", "tiny_torch"))),
        status=str(record.get("status", "completed")),
        started_at=str(record.get("started_at", "")),
        updated_at=str(record.get("updated_at", record.get("completed_at", ""))),
        completed_at=str(record.get("completed_at", "")),
        ticks_requested=int(record.get("tick_count_requested", summary.get("loop_ticks_completed", 0)) or 0),
        ticks_completed=int(record.get("tick_count_completed", summary.get("loop_ticks_completed", 0)) or 0),
        current_phase=_current_phase(state, events, default=str(record.get("status", "completed"))),
        policy_gate_state=_policy_gate_state(state, events),
        risk_score=_risk_score(state),
        confidence_score=_confidence_score(state),
        learning_steps=int(summary.get("learning_steps", _count_event_payload(events, "neural_learning_step_completed")) or 0),
        memory_records_written=int(record.get("memory_records_written", summary.get("memory_records_written", 0)) or 0),
        visual_events_emitted=int(record.get("visual_events_emitted", summary.get("visual_events_emitted", len(events))) or 0),
        replay_artifact_path=str(record.get("replay_artifact_path", summary.get("replay_artifact_path", ""))),
        run_record_path=str(record.get("run_record_path", "")),
        bundle_path=str(record.get("bundle_path", "")),
        gpu_evidence_status=str(record.get("gpu_evidence_status", summary.get("gpu_evidence_status", _gpu_evidence_status(root_path)))),
        public_alpha_gate_status=_gate_status(root_path),
        warnings=_warnings(root_path, str(record.get("gpu_evidence_status", summary.get("gpu_evidence_status", "")))),
        event_category_counts=event_category_counts(events),
    )


def summarize_supervisor_record(root: str | Path, record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Normalize a supervisor state record into the dashboard contract."""

    root_path = Path(root).resolve()
    replay = _read_json(_resolve(root_path, str(record.get("replay_artifact_path", ""))))
    events = _events_from_payload(replay)
    state = dict(replay.get("state", {})) if isinstance(replay.get("state", {}), Mapping) else {}
    return _run_contract(
        root_path,
        run_id=str(record.get("run_id", "")),
        run_kind="supervisor",
        agent_id=str(record.get("agent_id", "")),
        session_id=str(record.get("session_id", "")),
        supervisor_id=str(record.get("supervisor_id", "")),
        template=_template_from_replay(replay),
        flow_source="",
        backend=str(record.get("backend", "tiny_torch")),
        status=str(record.get("status", "completed")),
        started_at=str(record.get("started_at", "")),
        updated_at=str(record.get("updated_at", "")),
        completed_at=str(record.get("completed_at", "")),
        ticks_requested=int(record.get("max_ticks", 0) or 0),
        ticks_completed=int(record.get("ticks_completed", 0) or 0),
        current_phase=str(record.get("current_phase", _current_phase(state, events))),
        policy_gate_state=str(record.get("policy_gate_state", _policy_gate_state(state, events))),
        risk_score=_risk_score(state),
        confidence_score=_confidence_score(state),
        learning_steps=_count_event_payload(events, "neural_learning_step_completed"),
        memory_records_written=_memory_count(replay),
        visual_events_emitted=len(events),
        replay_artifact_path=str(record.get("replay_artifact_path", "")),
        run_record_path=str(record.get("run_record_path", "")),
        bundle_path="",
        gpu_evidence_status=str(record.get("gpu_evidence_status", _gpu_evidence_status(root_path))),
        public_alpha_gate_status=_gate_status(root_path),
        warnings=_warnings(root_path, str(record.get("gpu_evidence_status", ""))),
        event_category_counts=event_category_counts(events),
        last_heartbeat_at=str(record.get("last_heartbeat_at", "")),
    )


def event_category_counts(events: Sequence[Mapping[str, Any]]) -> Mapping[str, int]:
    """Count replay events by dashboard category."""

    counts: dict[str, int] = {category: 0 for category in ("neural", "policy", "memory", "action", "supervisor", "compute/economy", "audit/safety")}
    for event in events:
        event_type = str(event.get("event_type", ""))
        payload = dict(event.get("payload", {})) if isinstance(event.get("payload", {}), Mapping) else {}
        category = CATEGORY_ALIASES.get(event_type, event_type or "action")
        if event_type == "safety" or "policy" in str(payload.get("event", "")) or "policy" in str(payload.get("policy_gate_state", "")):
            counts["policy"] += 1
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def build_public_alpha_demo_bundle(root: str | Path = ".", out: str | Path = "artifacts/launch/bundles/public-alpha-local-demo.json") -> Mapping[str, Any]:
    """Write a lightweight local public-alpha demo bundle for Mission Control."""

    root_path = Path(root).resolve()
    output = Path(out)
    if not output.is_absolute():
        output = root_path / output
    console = list_run_console_runs(root_path)
    fixtures = run_console_fixtures(root_path)
    evidence_path = root_path / "release_evidence" / "public_alpha_launch.json"
    evidence = _read_json(evidence_path)
    local_public_alpha = _gate_status(root_path)
    gpu_status = _gpu_evidence_status(root_path)
    bundle_without_hash: dict[str, Any] = {
        "ok": True,
        "schema_version": PUBLIC_ALPHA_DEMO_BUNDLE_VERSION,
        "project": {
            "name": "Flow Memory",
            "tagline": "The Human Compute Network",
            "core_loop": "perceive -> predict -> remember -> reason -> act -> evaluate -> learn -> transact",
        },
        "generated_at": _now(),
        "local_public_alpha_status": local_public_alpha,
        "gpu_evidence_status": gpu_status,
        "warnings": _warnings(root_path, gpu_status),
        "launchpad_summary": _fixture_summary(fixtures, "live-neural-agent-launch"),
        "operations_registry_summary": _fixture_summary(fixtures, "live-agent-operations"),
        "supervisor_summary": _fixture_summary(fixtures, "live-agent-supervisor"),
        "mission_control_fixtures": tuple(dict(item) for item in fixtures.get("fixtures", ())),
        "run_console": {"run_count": console.get("run_count", 0), "runs": console.get("runs", ())},
        "docs": {
            "start_here": "docs/START_HERE.md",
            "launchpad": "docs/LIVE_AGENT_LAUNCHPAD.md",
            "neural_live_agents": "docs/NEURAL_LIVE_AGENTS.md",
            "mission_control": "docs/MISSION_CONTROL_QUICKSTART.md",
            "public_alpha_readiness": "docs/PUBLIC_ALPHA_READINESS.md",
        },
        "release_evidence": {
            "path": _rel(root_path, evidence_path),
            "ok": bool(evidence),
            "hash": evidence.get("hash", "") if evidence else "",
        },
        "commands": _demo_commands(),
        "invariants": {
            "local_only": True,
            "neural_advisory_only": True,
            "policy_gated": True,
            "approval_gate_authoritative": True,
            "no_external_model_calls": True,
            "no_live_provider_calls": True,
            "no_private_keys": True,
            "no_funds_moved": True,
            "no_broadcast": True,
            "no_live_settlement": True,
            "gpu_gated_release_requires_real_runpod_artifact": True,
        },
    }
    bundle_hash = hashlib.sha256(json.dumps(bundle_without_hash, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    bundle = {**bundle_without_hash, "bundle_hash": bundle_hash, "bundle_path": _rel(root_path, output)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return bundle


def _summary_from_fixture_payload(root: Path, spec: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    path = root / str(spec["path"])
    events = _events_from_payload(payload)
    state = dict(payload.get("state", {})) if isinstance(payload.get("state", {}), Mapping) else {}
    summary = dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {}
    run_record = dict(payload.get("run_record", {})) if isinstance(payload.get("run_record", {}), Mapping) else {}
    supervisor = dict(payload.get("supervisor", {})) if isinstance(payload.get("supervisor", {}), Mapping) else {}
    embodiment = dict(payload.get("embodiment", {})) if isinstance(payload.get("embodiment", {}), Mapping) else {}
    source = embodiment or supervisor or run_record or summary
    run_id = str(source.get("run_id", spec["fixture_id"]))
    agent_id = str(source.get("agent_id", summary.get("agent_id", _first_agent_id(state))))
    return _run_contract(
        root,
        run_id=run_id or str(spec["fixture_id"]),
        run_kind=str(spec["run_kind"]),
        agent_id=agent_id,
        session_id=str(source.get("session_id", summary.get("session_id", _first_neural(state).get("session_id", "")))),
        supervisor_id=str(supervisor.get("supervisor_id", "")),
        template=str(source.get("template", summary.get("template", _template_from_replay(payload)))),
        flow_source=str(source.get("flow_source", "")),
        backend=str(source.get("backend", summary.get("backend", _first_neural(state).get("backend", "tiny_torch")))),
        status=str(source.get("status", "completed" if payload.get("ok", True) else "missing")),
        started_at=str(source.get("started_at", "")),
        updated_at=str(source.get("updated_at", source.get("completed_at", payload.get("generated_at", "")))),
        completed_at=str(source.get("completed_at", payload.get("generated_at", ""))),
        ticks_requested=int(source.get("tick_count_requested", supervisor.get("max_ticks", summary.get("loop_ticks_completed", 0))) or 0),
        ticks_completed=int(source.get("tick_count_completed", supervisor.get("ticks_completed", summary.get("loop_ticks_completed", 0))) or 0),
        current_phase=str(supervisor.get("current_phase", _current_phase(state, events, str(source.get("status", "completed"))))),
        policy_gate_state=str(supervisor.get("policy_gate_state", _policy_gate_state(state, events))),
        risk_score=_risk_score(state),
        confidence_score=_confidence_score(state),
        learning_steps=int(summary.get("learning_steps", _count_event_payload(events, "neural_learning_step_completed")) or 0),
        memory_records_written=int(source.get("memory_records_written", summary.get("memory_records_written", _memory_count(payload))) or 0),
        visual_events_emitted=int(source.get("visual_events_emitted", summary.get("visual_events_emitted", len(events))) or 0),
        replay_artifact_path=str(source.get("replay_artifact_path", spec["path"])),
        run_record_path=str(source.get("run_record_path", "")),
        bundle_path=str(source.get("bundle_path", "")),
        gpu_evidence_status=str(source.get("gpu_evidence_status", summary.get("gpu_evidence_status", _gpu_evidence_status(root)))),
        public_alpha_gate_status=_gate_status(root),
        warnings=_warnings(root, str(source.get("gpu_evidence_status", summary.get("gpu_evidence_status", "")))),
        event_category_counts=event_category_counts(events),
        fixture_id=str(spec["fixture_id"]),
        label=str(spec["label"]),
        description=str(spec["description"]),
        fixture_path=_rel(root, path),
        ok=path.exists() and bool(payload.get("ok", True)) and bool(events or state),
    )


def _run_contract(root: Path, **values: Any) -> Mapping[str, Any]:
    defaults = {
        "run_id": "",
        "run_kind": "operations",
        "agent_id": "",
        "session_id": "",
        "supervisor_id": "",
        "template": "",
        "flow_source": "",
        "backend": "tiny_torch",
        "status": "observed",
        "started_at": "",
        "updated_at": "",
        "completed_at": "",
        "ticks_requested": 0,
        "ticks_completed": 0,
        "current_phase": "observed",
        "policy_gate_state": "applied",
        "risk_score": 0.0,
        "confidence_score": 0.0,
        "learning_steps": 0,
        "memory_records_written": 0,
        "visual_events_emitted": 0,
        "replay_artifact_path": "",
        "run_record_path": "",
        "bundle_path": "",
        "gpu_evidence_status": _gpu_evidence_status(root),
        "public_alpha_gate_status": _gate_status(root),
        "warnings": _warnings(root, ""),
        "event_category_counts": {},
        "local_only": True,
        "neural_advisory_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }
    merged = {**defaults, **values}
    return merged


def _events_from_payload(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    events = payload.get("events", payload.get("visual_events", ()))
    if isinstance(events, (list, tuple)):
        return tuple(event for event in events if isinstance(event, Mapping))
    return ()


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _resolve(root: Path, value: str) -> Path:
    if not value:
        return root / "__missing__"
    path = Path(value)
    return path if path.is_absolute() else root / path


def _first_neural(state: Mapping[str, Any]) -> Mapping[str, Any]:
    neural = state.get("neural", ())
    if isinstance(neural, (list, tuple)) and neural and isinstance(neural[0], Mapping):
        return dict(neural[0])
    return {}


def _first_agent_id(state: Mapping[str, Any]) -> str:
    agents = state.get("agents", ())
    if isinstance(agents, (list, tuple)) and agents and isinstance(agents[0], Mapping):
        return str(agents[0].get("agent_id", ""))
    return ""


def _current_phase(state: Mapping[str, Any], events: Sequence[Mapping[str, Any]], default: str = "observed") -> str:
    supervisor = state.get("supervisor", ())
    if isinstance(supervisor, (list, tuple)) and supervisor and isinstance(supervisor[-1], Mapping):
        return str(supervisor[-1].get("current_phase", default))
    neural = state.get("neural", ())
    if isinstance(neural, (list, tuple)) and neural and isinstance(neural[-1], Mapping):
        return str(neural[-1].get("phase", default))
    if events:
        payload = events[-1].get("payload", {})
        if isinstance(payload, Mapping):
            return str(payload.get("phase", payload.get("current_phase", default)))
    return default


def _policy_gate_state(state: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> str:
    supervisor = state.get("supervisor", ())
    if isinstance(supervisor, (list, tuple)) and supervisor and isinstance(supervisor[-1], Mapping):
        value = str(supervisor[-1].get("policy_gate_state", ""))
        if value:
            return value
    neural = state.get("neural", ())
    if isinstance(neural, (list, tuple)) and neural and isinstance(neural[-1], Mapping):
        value = str(neural[-1].get("policy_gate_state", ""))
        if value:
            return value
    safety = state.get("safety", ())
    if isinstance(safety, (list, tuple)) and safety and isinstance(safety[-1], Mapping):
        return str(safety[-1].get("decision", "applied"))
    return "applied" if events else "not_observed"


def _risk_score(state: Mapping[str, Any]) -> float:
    neural = state.get("neural", ())
    risks = [float(item.get("risk_score", 0.0) or 0.0) for item in neural if isinstance(item, Mapping)] if isinstance(neural, (list, tuple)) else []
    safety = state.get("safety", ())
    for item in safety if isinstance(safety, (list, tuple)) else ():
        if not isinstance(item, Mapping):
            continue
        if str(item.get("decision", "")).lower() in {"blocked", "denied"} or str(item.get("risk_level", "")).lower() == "high":
            risks.append(1.0)
        elif bool(item.get("requires_approval")):
            risks.append(0.72)
    return _clamp(max(risks) if risks else 0.0)


def _confidence_score(state: Mapping[str, Any]) -> float:
    neural = state.get("neural", ())
    values = [float(item.get("prediction_confidence", 0.0) or 0.0) for item in neural if isinstance(item, Mapping)] if isinstance(neural, (list, tuple)) else []
    return _clamp(max(values) if values else 0.0)


def _count_event_payload(events: Sequence[Mapping[str, Any]], event_name: str) -> int:
    count = 0
    for event in events:
        payload = event.get("payload", {})
        if isinstance(payload, Mapping) and payload.get("event") == event_name:
            count += 1
    return count


def _memory_count(payload: Mapping[str, Any]) -> int:
    memory_records = payload.get("memory_records", ())
    if isinstance(memory_records, (list, tuple)):
        return len(memory_records)
    state = dict(payload.get("state", {})) if isinstance(payload.get("state", {}), Mapping) else {}
    memory = state.get("memory", ())
    return len(memory) if isinstance(memory, (list, tuple)) else 0


def _template_from_replay(payload: Mapping[str, Any]) -> str:
    template = payload.get("template", {})
    if isinstance(template, Mapping):
        return str(template.get("name", ""))
    return ""


def _fixture_summary(fixtures: Mapping[str, Any], fixture_id: str) -> Mapping[str, Any]:
    for item in fixtures.get("fixtures", ()):  # type: ignore[union-attr]
        if isinstance(item, Mapping) and item.get("fixture_id") == fixture_id:
            return dict(item.get("summary", {})) if isinstance(item.get("summary", {}), Mapping) else {}
    return {}


def _gate_status(root: Path) -> Mapping[str, Any]:
    evidence = _read_json(root / "release_evidence" / "public_alpha_launch.json")
    if evidence:
        ok = bool(evidence)
        return {
            "target": "local-public-alpha",
            "ok": ok,
            "classification": "local_public_alpha_evidence" if ok else "local_public_alpha_evidence_pending",
            "blockers": tuple(evidence.get("blockers", ())) if isinstance(evidence.get("blockers", ()), (list, tuple)) else (),
        }
    return {
        "target": "local-public-alpha",
        "ok": False,
        "classification": "not_evaluated",
        "blockers": ("public_alpha_launch_evidence_missing",),
    }


def _gpu_evidence_status(root: Path) -> str:
    evidence_path = root / "release_evidence" / "bundle" / "gpu_evidence.json"
    evidence = _read_json(evidence_path)
    for record in evidence.get("runs", ()):  # type: ignore[union-attr]
        if not isinstance(record, Mapping) or record.get("ok") is not True:
            continue
        summary = dict(record.get("summary", {})) if isinstance(record.get("summary", {}), Mapping) else {}
        if not summary.get("skipped") and (summary.get("cuda_available") is True or summary.get("cli_neural_status") == "available"):
            return "verified"
    artifact = root / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    if artifact.exists():
        return "artifact_present_not_verified"
    return "blocked_missing_artifact"


def _warnings(root: Path, gpu_status: str) -> tuple[str, ...]:
    status = gpu_status or _gpu_evidence_status(root)
    warnings = [
        "local deterministic public-alpha demo only",
        "neural outputs are advisory and policy-gated",
        "no live provider calls, real funds, private keys, broadcasts, or live settlement",
    ]
    if status != "verified":
        warnings.append("GPU-gated neural release remains blocked until the real RunPod artifact is imported and verified")
    return tuple(warnings)


def _demo_commands() -> tuple[Mapping[str, Any], ...]:
    return (
        {"label": "Launch local neural-live agent", "command": "python -m flow_memory launch agent --template live-research --neural tiny_torch --ticks 5 --emit-visual --json"},
        {"label": "List launch runs", "command": "python -m flow_memory launch runs list --json"},
        {"label": "Show one launch run", "command": "python -m flow_memory launch runs show <run_id> --json"},
        {"label": "Replay one launch run", "command": "python -m flow_memory launch runs replay <run_id> --json"},
        {"label": "Export one launch run", "command": "python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json"},
        {"label": "Start bounded supervisor", "command": "python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 5 --tick-interval-ms 10 --emit-visual --json"},
        {"label": "Supervisor status", "command": "python -m flow_memory launch supervisor status --json"},
        {"label": "Supervisor heartbeat", "command": "python -m flow_memory launch supervisor heartbeat <run_id> --json"},
        {"label": "Pause supervisor", "command": "python -m flow_memory launch supervisor pause <run_id> --json"},
        {"label": "Resume supervisor as continuation", "command": "python -m flow_memory launch supervisor resume <run_id> --ticks 5 --json"},
        {"label": "Stop supervisor", "command": "python -m flow_memory launch supervisor stop <run_id> --json"},
        {"label": "Launch doctor", "command": "python -m flow_memory launch doctor --json"},
        {"label": "Build public-alpha local demo bundle", "command": "python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json"},
        {"label": "Refresh Live 3D embodiment fixture", "command": "python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json"},
        {"label": "Finalize public-alpha handoff", "command": "python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json"},
        {"label": "Dashboard checks", "command": "cd dashboard && npm test && npm run build"},
    )


def _clamp(value: float) -> float:
    if value != value:
        return 0.0
    return max(0.0, min(1.0, value))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
