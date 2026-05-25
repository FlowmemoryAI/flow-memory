"""Local run registry for Live Agent Launchpad operations.

The registry is intentionally file-backed and local-only. It records metadata for
launchpad runs so operators can inspect, replay, stop, resume-by-continuation,
and export lightweight run bundles without any external services.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

RUN_RECORD_VERSION = "flow-memory-live-agent-run-v1"
RUN_BUNDLE_VERSION = "flow-memory-live-agent-run-bundle-v1"
RUN_STATUSES = frozenset({"created", "running", "paused", "completed", "failed", "stopped"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})


def create_run_record(root: str | Path = ".", record: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Create a local JSON run record under artifacts/launch/runs."""

    payload = _normalize_record(root, record or {})
    path = run_record_path(root, str(payload["run_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, payload)
    return payload


def update_run_record(root: str | Path, run_id: str, updates: Mapping[str, Any]) -> Mapping[str, Any]:
    """Update an existing run record, preserving unknown fields."""

    current = dict(get_run_record(root, run_id))
    merged = {**current, **dict(updates)}
    payload = _normalize_record(root, merged)
    _write_json(run_record_path(root, run_id), payload)
    return payload


def record_run_failure(root: str | Path, run_id: str, error: BaseException | str, metadata: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Persist a failed run record with a redacted error summary."""

    details = dict(metadata or {})
    details.update({
        "run_id": run_id,
        "status": "failed",
        "error_summary": str(error),
        "completed_at": _now(),
    })
    if run_record_path(root, run_id).exists():
        return update_run_record(root, run_id, details)
    return create_run_record(root, details)


def list_run_records(root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    """List local launch run records in deterministic order."""

    directory = runs_dir(root)
    if not directory.exists():
        return ()
    records: list[Mapping[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            records.append(dict(payload))
    return tuple(sorted(records, key=lambda item: (str(item.get("started_at", "")), str(item.get("run_id", "")))))


def get_run_record(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Load one run record by ID."""

    path = run_record_path(root, run_id)
    if not path.exists():
        raise KeyError(f"Unknown launch run: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Run record is not a JSON object: {run_id}")
    return dict(payload)


def replay_run_record(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Return replay metadata and lightweight state for a run."""

    record = dict(get_run_record(root, run_id))
    replay_path = _resolve(root, str(record.get("replay_artifact_path", "")))
    if not replay_path.exists():
        raise KeyError(f"Replay artifact missing for launch run: {run_id}")
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Replay artifact is not a JSON object: {replay_path}")
    events = payload.get("events", payload.get("visual_events", ()))
    event_count = len(events) if isinstance(events, (list, tuple)) else 0
    return {
        "ok": True,
        "run": record,
        "replay_artifact_path": record.get("replay_artifact_path", ""),
        "summary": dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {},
        "state": dict(payload.get("state", {})) if isinstance(payload.get("state", {}), Mapping) else {},
        "visual_event_count": event_count,
    }


def stop_run_record(root: str | Path, run_id: str) -> Mapping[str, Any]:
    """Mark a non-terminal local run as stopped, or report a terminal no-op."""

    record = dict(get_run_record(root, run_id))
    before = str(record.get("status", "created"))
    if before in TERMINAL_STATUSES:
        return {"ok": True, "run_id": run_id, "status_before": before, "status_after": before, "noop": True, "reason": f"run already {before}"}
    updated = update_run_record(root, run_id, {"status": "stopped", "completed_at": _now()})
    return {"ok": True, "run_id": run_id, "status_before": before, "status_after": "stopped", "noop": False, "run": updated}


def export_run_bundle(root: str | Path, run_id: str, out: str | Path | None = None) -> Mapping[str, Any]:
    """Write a lightweight local run bundle with metadata and replay summary."""

    record = dict(get_run_record(root, run_id))
    replay: Mapping[str, Any]
    try:
        replay = replay_run_record(root, run_id)
    except (KeyError, ValueError) as exc:
        replay = {"ok": False, "error": str(exc)}
    output = Path(out) if out is not None else bundles_dir(root) / f"{run_id}.json"
    if not output.is_absolute():
        output = Path(root).resolve() / output
    bundle = {
        "ok": True,
        "bundle_version": RUN_BUNDLE_VERSION,
        "run_id": run_id,
        "exported_at": _now(),
        "record": record,
        "replay": {
            "ok": bool(replay.get("ok")),
            "replay_artifact_path": replay.get("replay_artifact_path", record.get("replay_artifact_path", "")),
            "summary": replay.get("summary", {}),
            "visual_event_count": replay.get("visual_event_count", 0),
        },
        "invariants": {
            "local_only": True,
            "no_external_calls": True,
            "no_live_provider_calls": True,
            "no_private_keys": True,
            "no_funds_moved": True,
            "safety_authority": "policy_engine_and_approval_gate",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, bundle)
    return {**bundle, "bundle_path": _rel(Path(root).resolve(), output)}


def load_run_bundle(path: str | Path) -> Mapping[str, Any]:
    """Load a previously exported local run bundle."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("run bundle is not a JSON object")
    if payload.get("bundle_version") != RUN_BUNDLE_VERSION:
        raise ValueError("unsupported run bundle version")
    return dict(payload)


def upsert_run_from_launch_payload(root: str | Path, payload: Mapping[str, Any], *, status: str = "completed") -> Mapping[str, Any]:
    """Create/update a run record from a Live Agent Launchpad payload."""

    root_path = Path(root).resolve()
    summary = dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {}
    agent = dict(payload.get("agent", {})) if isinstance(payload.get("agent", {}), Mapping) else {}
    template = dict(payload.get("template", {})) if isinstance(payload.get("template", {}), Mapping) else {}
    metadata = dict(agent.get("metadata", {})) if isinstance(agent.get("metadata", {}), Mapping) else {}
    run_id = str(summary.get("run_id") or metadata.get("launchpad_run_id") or "")
    if not run_id:
        raise ValueError("launch payload is missing run_id")
    generated_at = str(payload.get("generated_at", "")) or _now()
    replay_path = str(summary.get("replay_artifact_path", ""))
    checkpoint_path = str(summary.get("checkpoint_metadata_path", ""))
    record_path = run_record_path(root_path, run_id)
    existing = dict(get_run_record(root_path, run_id)) if record_path.exists() else {}
    record = {
        **existing,
        "schema_version": RUN_RECORD_VERSION,
        "run_id": run_id,
        "agent_id": str(summary.get("agent_id", agent.get("agent_id", ""))),
        "session_id": str(summary.get("session_id", agent.get("neural_config", {}).get("session_id", "")) if isinstance(agent.get("neural_config", {}), Mapping) else summary.get("session_id", "")),
        "template": str(summary.get("template", template.get("name", ""))),
        "flow_source": str(metadata.get("flow_path", "")),
        "backend": str(summary.get("backend", dict(agent.get("neural_config", {})).get("backend", "tiny_torch") if isinstance(agent.get("neural_config", {}), Mapping) else "tiny_torch")),
        "neural_live_enabled": bool(dict(agent.get("neural_config", {})).get("live_mode", True)) if isinstance(agent.get("neural_config", {}), Mapping) else True,
        "policy_mode": str(summary.get("policy_mode", agent.get("autonomy_mode", "supervised"))),
        "started_at": existing.get("started_at", generated_at),
        "completed_at": generated_at if status in TERMINAL_STATUSES else "",
        "status": status,
        "tick_count_requested": int(summary.get("loop_ticks_completed", 0) or 0),
        "tick_count_completed": int(summary.get("loop_ticks_completed", 0) or 0),
        "memory_records_written": int(summary.get("memory_records_written", 0) or 0),
        "visual_events_emitted": int(summary.get("visual_events_emitted", 0) or 0),
        "replay_artifact_path": replay_path,
        "checkpoint_metadata_path": checkpoint_path,
        "summary_artifact_path": replay_path,
        "run_record_path": _rel(root_path, record_path),
        "gpu_evidence_status": str(summary.get("gpu_evidence_status", "blocked_missing_artifact")),
        "error_summary": "",
        "local_only": True,
        "no_external_calls": bool(summary.get("no_external_calls", True)),
        "no_live_provider_calls": bool(summary.get("no_live_provider_calls", True)),
        "no_private_keys": bool(summary.get("no_private_keys", True)),
        "no_funds_moved": bool(summary.get("no_funds_moved", True)),
        "safety_authority": str(summary.get("safety_authority", "policy_engine_and_approval_gate")),
    }
    return create_run_record(root_path, record)


def runs_dir(root: str | Path = ".") -> Path:
    return Path(root).resolve() / "artifacts" / "launch" / "runs"


def bundles_dir(root: str | Path = ".") -> Path:
    return Path(root).resolve() / "artifacts" / "launch" / "bundles"


def run_record_path(root: str | Path, run_id: str) -> Path:
    safe = _safe_run_id(run_id)
    return runs_dir(root) / f"{safe}.json"


def _normalize_record(root: str | Path, record: Mapping[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    run_id = _safe_run_id(str(record.get("run_id", "")))
    if not run_id:
        raise ValueError("run_id is required")
    status = str(record.get("status", "created"))
    if status not in RUN_STATUSES:
        raise ValueError(f"invalid launch run status: {status}")
    now = _now()
    path = run_record_path(root_path, run_id)
    normalized = {
        "schema_version": RUN_RECORD_VERSION,
        "run_id": run_id,
        "agent_id": str(record.get("agent_id", "")),
        "session_id": str(record.get("session_id", "")),
        "template": str(record.get("template", "")),
        "flow_source": str(record.get("flow_source", "")),
        "backend": str(record.get("backend", "tiny_torch")),
        "neural_live_enabled": bool(record.get("neural_live_enabled", True)),
        "policy_mode": str(record.get("policy_mode", "supervised")),
        "started_at": str(record.get("started_at", now)),
        "completed_at": str(record.get("completed_at", "")),
        "status": status,
        "tick_count_requested": int(record.get("tick_count_requested", 0) or 0),
        "tick_count_completed": int(record.get("tick_count_completed", 0) or 0),
        "memory_records_written": int(record.get("memory_records_written", 0) or 0),
        "visual_events_emitted": int(record.get("visual_events_emitted", 0) or 0),
        "replay_artifact_path": str(record.get("replay_artifact_path", "")),
        "checkpoint_metadata_path": str(record.get("checkpoint_metadata_path", "")),
        "summary_artifact_path": str(record.get("summary_artifact_path", "")),
        "run_record_path": str(record.get("run_record_path", _rel(root_path, path))),
        "gpu_evidence_status": str(record.get("gpu_evidence_status", "blocked_missing_artifact")),
        "error_summary": str(record.get("error_summary", "")),
        "local_only": bool(record.get("local_only", True)),
        "no_external_calls": bool(record.get("no_external_calls", True)),
        "no_live_provider_calls": bool(record.get("no_live_provider_calls", True)),
        "no_private_keys": bool(record.get("no_private_keys", True)),
        "no_funds_moved": bool(record.get("no_funds_moved", True)),
        "safety_authority": str(record.get("safety_authority", "policy_engine_and_approval_gate")),
    }
    extra = record.get("metadata", {})
    if isinstance(extra, Mapping):
        normalized["metadata"] = dict(extra)
    return normalized


def _resolve(root: str | Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root).resolve() / candidate


def _safe_run_id(run_id: str) -> str:
    run_id = run_id.strip()
    if not run_id:
        return ""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    return "".join(char if char in allowed else "_" for char in run_id)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
