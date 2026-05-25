"""Bounded local supervisor for Live Agent Operations.

The supervisor is intentionally synchronous, finite, and artifact-backed. It does
not keep hidden background processes alive. A resume operation creates an honest
continuation run from prior metadata instead of pretending to resurrect a process.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from flow_memory.launch_operations import (
    get_run_record,
    run_record_path,
    update_run_record,
)
from flow_memory.launchpad import run_live_agent_launch
from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION, VisualEvent
from flow_memory.visualization.reducer import reduce_visual_events

SUPERVISOR_STATE_VERSION = "flow-memory-live-agent-supervisor-v1"
HEARTBEAT_VERSION = "flow-memory-live-agent-supervisor-heartbeat-v1"
SUPERVISOR_STATUSES = frozenset({"created", "running", "paused", "completed", "failed", "stopped"})
SUPERVISOR_TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})
DEFAULT_MAX_TICKS = 10


def start_supervised_run(
    *,
    template: str = "live-research",
    backend: str = "tiny_torch",
    ticks: int = DEFAULT_MAX_TICKS,
    tick_interval_ms: int = 250,
    emit_visual: bool = True,
    root: str | Path = ".",
    flow_path: str | Path | None = None,
    flow_source: str = "",
    goal: str = "",
    parent_run_id: str = "",
) -> Mapping[str, Any]:
    """Run a finite supervised local neural-live launch and persist supervisor state."""

    if ticks < 1:
        raise ValueError("ticks must be >= 1")
    if tick_interval_ms < 0:
        raise ValueError("tick_interval_ms must be >= 0")
    root_path = Path(root).resolve()
    started_at = _now()
    try:
        launch = run_live_agent_launch(
            template=template,
            flow_path=flow_path,
            flow_source=flow_source,
            goal=goal,
            backend=backend,
            ticks=ticks,
            emit_visual=emit_visual,
            root=root_path,
            write_artifact=True,
            write_checkpoint=True,
            write_run_record=True,
        )
        summary = dict(launch.get("summary", {})) if isinstance(launch.get("summary", {}), Mapping) else {}
        run_id = str(summary.get("run_id", ""))
        supervisor_id = _stable_id("supervisor", run_id)
        completed_at = str(launch.get("generated_at", "")) or _now()
        record = _supervisor_record(
            supervisor_id=supervisor_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            agent_id=str(summary.get("agent_id", "")),
            session_id=str(summary.get("session_id", "")),
            backend=str(summary.get("backend", backend)),
            status="completed",
            started_at=started_at,
            updated_at=completed_at,
            completed_at=completed_at,
            tick_interval_ms=tick_interval_ms,
            max_ticks=ticks,
            ticks_completed=int(summary.get("loop_ticks_completed", 0) or 0),
            current_phase="completed",
            policy_gate_state="applied",
            last_heartbeat_at=completed_at,
            replay_artifact_path=str(summary.get("replay_artifact_path", "")),
            run_record_path=str(summary.get("run_record_path", "")),
            continuation_of=parent_run_id,
            gpu_evidence_status=str(summary.get("gpu_evidence_status", "blocked_missing_artifact")),
        )
        heartbeat = _heartbeat_payload(record, status="completed", ticks=ticks)
        _write_heartbeat(root_path, run_id, heartbeat)
        launch = _attach_supervisor_visuals(root_path, launch, record, heartbeat)
        update_run_record(root_path, run_id, {
            "status": "completed",
            "metadata": {
                "supervisor_id": supervisor_id,
                "supervised": True,
                "parent_run_id": parent_run_id,
                "continuation_of": parent_run_id,
            },
            "visual_events_emitted": int(dict(launch.get("summary", {})).get("visual_events_emitted", record["ticks_completed"])),
        })
        _save_supervisor_record(root_path, record)
        return {
            "ok": True,
            "supervisor": record,
            "run": get_run_record(root_path, run_id),
            "heartbeat": heartbeat,
            "launch": launch,
            "replay_artifact_path": record["replay_artifact_path"],
            "local_only": True,
            "safety_authority": "policy_engine_and_approval_gate",
        }
    except Exception as exc:
        run_id = _stable_id("supervised_failed", template, backend, str(ticks), goal, flow_source, str(flow_path or ""))
        failed_at = _now()
        record = _supervisor_record(
            supervisor_id=_stable_id("supervisor", run_id),
            run_id=run_id,
            parent_run_id=parent_run_id,
            agent_id="",
            session_id="",
            backend=backend,
            status="failed",
            started_at=started_at,
            updated_at=failed_at,
            completed_at=failed_at,
            tick_interval_ms=tick_interval_ms,
            max_ticks=ticks,
            ticks_completed=0,
            current_phase="failed",
            policy_gate_state="fail_closed",
            last_heartbeat_at=failed_at,
            replay_artifact_path="",
            run_record_path=_rel(root_path, run_record_path(root_path, run_id)),
            continuation_of=parent_run_id,
            gpu_evidence_status=_gpu_evidence_status(root_path),
            last_error=type(exc).__name__,
        )
        heartbeat = _heartbeat_payload(record, status="failed", ticks=0)
        _write_heartbeat(root_path, run_id, heartbeat)
        _save_supervisor_record(root_path, record)
        raise


def supervisor_status(root: str | Path = ".") -> Mapping[str, Any]:
    """Return local supervisor registry status."""

    state = _load_state(Path(root).resolve())
    runs = dict(state.get("runs", {})) if isinstance(state.get("runs", {}), Mapping) else {}
    return {
        "ok": True,
        "schema_version": SUPERVISOR_STATE_VERSION,
        "latest_run_id": state.get("latest_run_id", ""),
        "run_count": len(runs),
        "runs": tuple(runs.values()),
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def get_supervisor_run(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Load one supervised run state."""

    state = _load_state(Path(root).resolve())
    runs = dict(state.get("runs", {})) if isinstance(state.get("runs", {}), Mapping) else {}
    record = runs.get(run_id)
    if not isinstance(record, Mapping):
        raise KeyError(f"Unknown supervisor run: {run_id}")
    return dict(record)


def get_supervisor_heartbeat(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Load heartbeat metadata for one supervised run."""

    path = heartbeat_path(root, run_id)
    if not path.exists():
        raise KeyError(f"Unknown supervisor heartbeat: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("heartbeat is not a JSON object")
    return dict(payload)


def pause_supervisor_run(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Pause a non-terminal supervised run, or return an honest terminal no-op."""

    root_path = Path(root).resolve()
    record = dict(get_supervisor_run(root_path, run_id))
    before = str(record.get("status", "created"))
    if before in SUPERVISOR_TERMINAL_STATUSES:
        return {"ok": True, "run_id": run_id, "status_before": before, "status_after": before, "noop": True, "reason": f"run already {before}"}
    if before == "paused":
        return {"ok": True, "run_id": run_id, "status_before": before, "status_after": before, "noop": True, "reason": "run already paused"}
    updated = {**record, "status": "paused", "current_phase": "paused", "updated_at": _now(), "policy_gate_state": "applied"}
    _save_supervisor_record(root_path, updated)
    _append_heartbeat(root_path, run_id, "live_supervisor_paused", updated)
    _try_update_run_record(root_path, run_id, {"status": "paused"})
    return {"ok": True, "run_id": run_id, "status_before": before, "status_after": "paused", "noop": False, "supervisor": updated}


def resume_supervisor_run(
    root: str | Path,
    run_id: str,
    *,
    ticks: int = 3,
    emit_visual: bool = True,
) -> Mapping[str, Any]:
    """Create a continuation run from prior supervised metadata."""

    root_path = Path(root).resolve()
    prior = dict(get_supervisor_run(root_path, run_id))
    if ticks < 1:
        raise ValueError("ticks must be >= 1")
    template = _template_from_run(root_path, run_id)
    resumed = start_supervised_run(
        template=template,
        backend=str(prior.get("backend", "tiny_torch") or "tiny_torch"),
        ticks=ticks,
        tick_interval_ms=int(prior.get("tick_interval_ms", 250) or 250),
        emit_visual=emit_visual,
        root=root_path,
        goal=f"Continue supervised run {run_id}",
        parent_run_id=run_id,
    )
    supervisor = dict(resumed.get("supervisor", {}))
    _append_heartbeat(root_path, str(supervisor.get("run_id", "")), "live_supervisor_continuation_created", supervisor)
    return {**resumed, "continued_from_run_id": run_id}


def stop_supervisor_run(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Stop a non-terminal supervised run, or return an honest terminal no-op."""

    root_path = Path(root).resolve()
    record = dict(get_supervisor_run(root_path, run_id))
    before = str(record.get("status", "created"))
    if before in SUPERVISOR_TERMINAL_STATUSES:
        return {"ok": True, "run_id": run_id, "status_before": before, "status_after": before, "noop": True, "reason": f"run already {before}"}
    updated = {**record, "status": "stopped", "current_phase": "stopped", "updated_at": _now(), "completed_at": _now(), "policy_gate_state": "applied"}
    _save_supervisor_record(root_path, updated)
    _append_heartbeat(root_path, run_id, "live_supervisor_stopped", updated)
    _try_update_run_record(root_path, run_id, {"status": "stopped", "completed_at": updated["completed_at"]})
    return {"ok": True, "run_id": run_id, "status_before": before, "status_after": "stopped", "noop": False, "supervisor": updated}


def supervisor_state_path(root: str | Path = ".") -> Path:
    return Path(root).resolve() / "artifacts" / "launch" / "supervisor" / "supervisor_state.json"


def heartbeat_path(root: str | Path, run_id: str) -> Path:
    return Path(root).resolve() / "artifacts" / "launch" / "supervisor" / "heartbeats" / f"{_safe_run_id(run_id)}.json"


def _supervisor_record(
    *,
    supervisor_id: str,
    run_id: str,
    parent_run_id: str,
    agent_id: str,
    session_id: str,
    backend: str,
    status: str,
    started_at: str,
    updated_at: str,
    completed_at: str,
    tick_interval_ms: int,
    max_ticks: int,
    ticks_completed: int,
    current_phase: str,
    policy_gate_state: str,
    last_heartbeat_at: str,
    replay_artifact_path: str,
    run_record_path: str,
    continuation_of: str,
    gpu_evidence_status: str,
    last_error: str = "",
) -> dict[str, Any]:
    if status not in SUPERVISOR_STATUSES:
        raise ValueError(f"invalid supervisor status: {status}")
    return {
        "schema_version": SUPERVISOR_STATE_VERSION,
        "supervisor_id": supervisor_id,
        "run_id": _safe_run_id(run_id),
        "parent_run_id": parent_run_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "backend": backend,
        "status": status,
        "started_at": started_at,
        "updated_at": updated_at,
        "completed_at": completed_at,
        "tick_interval_ms": int(tick_interval_ms),
        "max_ticks": int(max_ticks),
        "ticks_completed": int(ticks_completed),
        "current_phase": current_phase,
        "policy_gate_state": policy_gate_state,
        "last_heartbeat_at": last_heartbeat_at,
        "last_error": last_error,
        "replay_artifact_path": replay_artifact_path,
        "run_record_path": run_record_path,
        "continuation_of": continuation_of,
        "gpu_evidence_status": gpu_evidence_status,
        "local_only": True,
        "no_external_calls": True,
        "no_live_provider_calls": True,
        "no_private_keys": True,
        "no_funds_moved": True,
        "bounded": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def _heartbeat_payload(record: Mapping[str, Any], *, status: str, ticks: int) -> dict[str, Any]:
    events = [
        _heartbeat_event(record, "live_supervisor_started", 0, "created"),
    ]
    for tick in range(1, int(ticks) + 1):
        events.append(_heartbeat_event(record, "live_supervisor_tick_started", tick, "running"))
        events.append(_heartbeat_event(record, "live_supervisor_tick_completed", tick, "running"))
        events.append(_heartbeat_event(record, "live_supervisor_heartbeat", tick, "running"))
    final_event = "live_supervisor_completed" if status == "completed" else "live_supervisor_failed" if status == "failed" else "live_supervisor_stopped"
    events.append(_heartbeat_event(record, final_event, int(ticks), status))
    return {
        "ok": True,
        "schema_version": HEARTBEAT_VERSION,
        "run_id": record.get("run_id", ""),
        "supervisor_id": record.get("supervisor_id", ""),
        "status": status,
        "ticks_completed": int(record.get("ticks_completed", 0) or 0),
        "max_ticks": int(record.get("max_ticks", 0) or 0),
        "last_heartbeat_at": record.get("last_heartbeat_at", ""),
        "events": tuple(events),
        "local_only": True,
    }


def _heartbeat_event(record: Mapping[str, Any], event: str, tick: int, status: str) -> dict[str, Any]:
    return {
        "event": event,
        "run_id": record.get("run_id", ""),
        "supervisor_id": record.get("supervisor_id", ""),
        "agent_id": record.get("agent_id", ""),
        "session_id": record.get("session_id", ""),
        "backend": record.get("backend", "tiny_torch"),
        "tick": tick,
        "status": status,
        "current_phase": "heartbeat" if event == "live_supervisor_heartbeat" else event.replace("live_supervisor_", ""),
        "policy_gate_state": record.get("policy_gate_state", "applied"),
        "created_at": _stable_timestamp(tick, len(event)),
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def _write_heartbeat(root: Path, run_id: str, payload: Mapping[str, Any]) -> None:
    path = heartbeat_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def _append_heartbeat(root: Path, run_id: str, event: str, record: Mapping[str, Any]) -> None:
    try:
        payload = dict(get_supervisor_heartbeat(root, run_id))
        events = list(payload.get("events", ()))
    except (KeyError, ValueError, json.JSONDecodeError):
        payload = _heartbeat_payload(record, status=str(record.get("status", "created")), ticks=int(record.get("ticks_completed", 0) or 0))
        events = list(payload.get("events", ()))
    events.append(_heartbeat_event(record, event, int(record.get("ticks_completed", 0) or 0), str(record.get("status", "observed"))))
    payload["events"] = tuple(events)
    payload["status"] = record.get("status", payload.get("status", "observed"))
    _write_heartbeat(root, run_id, payload)


def _attach_supervisor_visuals(root: Path, launch: Mapping[str, Any], record: Mapping[str, Any], heartbeat: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = dict(launch)
    existing_events = tuple(payload.get("events", payload.get("visual_events", ())))
    supervisor_events = tuple(_visual_event_from_heartbeat(record, item) for item in heartbeat.get("events", ()) if isinstance(item, Mapping))
    all_events = tuple(existing_events) + tuple(event.as_record() for event in supervisor_events)
    payload["events"] = all_events
    payload["visual_events"] = all_events
    payload["state"] = reduce_visual_events(all_events, provenance="replay").as_record()
    payload["supervisor"] = dict(record)
    summary = dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {}
    summary["visual_events_emitted"] = len(all_events)
    summary["supervisor_id"] = record.get("supervisor_id", "")
    summary["supervisor_status"] = record.get("status", "")
    summary["heartbeat_artifact_path"] = _rel(root, heartbeat_path(root, str(record.get("run_id", ""))))
    payload["summary"] = summary
    replay_path = root / str(summary.get("replay_artifact_path", ""))
    if str(summary.get("replay_artifact_path", "")):
        replay_path.parent.mkdir(parents=True, exist_ok=True)
        replay_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return payload


def _visual_event_from_heartbeat(record: Mapping[str, Any], heartbeat: Mapping[str, Any]) -> VisualEvent:
    event_name = str(heartbeat.get("event", "live_supervisor_heartbeat"))
    tick = int(heartbeat.get("tick", 0) or 0)
    payload = {
        "event": event_name,
        "supervisor_id": record.get("supervisor_id", ""),
        "run_id": record.get("run_id", ""),
        "parent_run_id": record.get("parent_run_id", ""),
        "agent_id": record.get("agent_id", ""),
        "session_id": record.get("session_id", ""),
        "backend": record.get("backend", "tiny_torch"),
        "status": heartbeat.get("status", record.get("status", "observed")),
        "current_phase": heartbeat.get("current_phase", record.get("current_phase", "observed")),
        "tick": tick,
        "ticks_completed": min(tick, int(record.get("ticks_completed", 0) or 0)),
        "max_ticks": int(record.get("max_ticks", 0) or 0),
        "policy_gate_state": heartbeat.get("policy_gate_state", record.get("policy_gate_state", "applied")),
        "last_heartbeat_at": heartbeat.get("created_at", record.get("last_heartbeat_at", "")),
        "local_only": True,
        "bounded": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }
    return VisualEvent(
        event_type="supervisor",
        source=str(record.get("run_id", "")),
        payload=payload,
        provenance="replay",
        source_event_id=str(record.get("run_id", "")),
        event_id=_stable_id("visual_event", str(record.get("run_id", "")), event_name, str(tick)),
        created_at=str(heartbeat.get("created_at", _stable_timestamp(tick, 0))),
    )


def _save_supervisor_record(root: Path, record: Mapping[str, Any]) -> None:
    state = _load_state(root)
    runs = dict(state.get("runs", {})) if isinstance(state.get("runs", {}), Mapping) else {}
    runs[str(record["run_id"])] = dict(record)
    state = {
        "schema_version": SUPERVISOR_STATE_VERSION,
        "latest_run_id": str(record["run_id"]),
        "updated_at": _now(),
        "current": dict(record),
        "runs": runs,
        "local_only": True,
    }
    path = supervisor_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def _load_state(root: Path) -> Mapping[str, Any]:
    path = supervisor_state_path(root)
    if not path.exists():
        return {"schema_version": SUPERVISOR_STATE_VERSION, "latest_run_id": "", "runs": {}, "local_only": True}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("supervisor state is not a JSON object")
    return dict(payload)


def _try_update_run_record(root: Path, run_id: str, updates: Mapping[str, Any]) -> None:
    try:
        update_run_record(root, run_id, updates)
    except (KeyError, ValueError):
        return


def _template_from_run(root: Path, run_id: str) -> str:
    try:
        record = get_run_record(root, run_id)
    except KeyError:
        record = get_supervisor_run(root, run_id)
    template = str(record.get("template", "") or "live-research")
    return template if template else "live-research"


def _gpu_evidence_status(root: Path) -> str:
    artifact = root / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    if not artifact.exists():
        return "blocked_missing_artifact"
    return "artifact_present_not_verified"


def _safe_run_id(run_id: str) -> str:
    run_id = str(run_id).strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    return "".join(char if char in allowed else "_" for char in run_id)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _stable_timestamp(tick: int, ordinal: int) -> str:
    return f"2026-01-01T01:{tick % 60:02d}:{ordinal % 60:02d}+00:00"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
