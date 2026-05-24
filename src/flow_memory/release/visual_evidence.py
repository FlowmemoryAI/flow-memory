"""Mission Control visual-system evidence for release bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import endpoint_manifest
from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION

_VISUAL_ENDPOINTS = (
    "/visual/state",
    "/visual/events",
    "/visual/schema",
    "/visual/replay/{run_id}",
    "/network/state",
    "/network/run-scenario",
)

_REQUIRED_FILES = (
    "src/flow_memory/visualization/events.py",
    "src/flow_memory/visualization/reducer.py",
    "src/flow_memory/visualization/layout.py",
    "src/flow_memory/api/visual_endpoints.py",
    "scripts/export_visual_replay.py",
    "dashboard/src/app/mission-control/page.tsx",
    "dashboard/src/mock-data/local-network-replay.json",
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/VISUAL_TELEMETRY_SCHEMA.md",
)


def visual_system_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    """Return deterministic evidence for the public-alpha Mission Control path."""

    root_path = Path(root).resolve()
    file_records = tuple(_file_record(root_path, relative) for relative in _REQUIRED_FILES)
    replay = _replay_record(root_path / "dashboard" / "src" / "mock-data" / "local-network-replay.json", root_path)
    endpoints = _endpoint_record()
    ok = (
        all(record["exists"] for record in file_records)
        and bool(replay.get("ok"))
        and bool(endpoints.get("ok"))
    )
    blockers: list[str] = []
    blockers.extend(f"missing_{record['path'].replace('/', '_')}" for record in file_records if not record["exists"])
    if not replay.get("ok"):
        blockers.append(str(replay.get("blocker", "visual_replay_invalid")))
    if not endpoints.get("ok"):
        blockers.append("visual_api_endpoints_missing")
    return {
        "ok": ok,
        "schema_version": VISUAL_SCHEMA_VERSION,
        "files": file_records,
        "endpoints": endpoints,
        "replay": replay,
        "blockers": tuple(blockers),
    }


def verify_visual_system_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    files = tuple(evidence.get("files", ()))
    endpoints = dict(evidence.get("endpoints", {}))
    replay = dict(evidence.get("replay", {}))
    missing_files = tuple(record.get("path") for record in files if not record.get("exists"))
    missing_endpoints = tuple(endpoints.get("missing", ()))
    ok = not missing_files and not missing_endpoints and bool(replay.get("ok"))
    return {
        "ok": ok,
        "missing_files": missing_files,
        "missing_endpoints": missing_endpoints,
        "replay_ok": bool(replay.get("ok")),
    }


def _file_record(root: Path, relative: str) -> Mapping[str, Any]:
    path = root / relative
    if not path.exists():
        return {"path": relative, "exists": False, "sha256": "", "bytes": 0}
    data = path.read_bytes()
    return {
        "path": relative,
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _replay_record(path: Path, root: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {"ok": False, "blocker": "visual_replay_missing", "path": str(path.relative_to(root))}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "blocker": "visual_replay_invalid_json", "path": str(path.relative_to(root))}
    if not isinstance(payload, Mapping):
        return {"ok": False, "blocker": "visual_replay_not_object", "path": str(path.relative_to(root))}
    state = dict(payload.get("state", {}))
    metadata = dict(payload.get("metadata", {}))
    events = tuple(payload.get("events", ()))
    ok = (
        payload.get("ok") is True
        and payload.get("schema_version") == VISUAL_SCHEMA_VERSION
        and payload.get("provenance") == "replay"
        and bool(state.get("agents"))
        and bool(state.get("tasks"))
        and bool(events)
    )
    data = path.read_bytes()
    return {
        "ok": ok,
        "blocker": "" if ok else "visual_replay_invalid",
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "event_count": len(events),
        "agent_count": int(metadata.get("agent_count", len(state.get("agents", ())))),
        "task_count": int(metadata.get("task_count", len(state.get("tasks", ())))),
    }


def _endpoint_record() -> Mapping[str, Any]:
    paths = {str(endpoint.get("path", "")) for endpoint in endpoint_manifest().get("endpoints", ()) if isinstance(endpoint, Mapping)}
    missing = tuple(path for path in _VISUAL_ENDPOINTS if path not in paths)
    present = tuple(path for path in _VISUAL_ENDPOINTS if path in paths)
    return {"ok": not missing, "present": present, "missing": missing}
