"""Validate Mission Control visual replay JSON artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION


def validate_visual_replay(path: str | Path) -> Mapping[str, Any]:
    replay_path = Path(path)
    blockers: list[str] = []
    if not replay_path.exists():
        return {"ok": False, "path": str(replay_path), "blockers": ("visual_replay_missing",)}
    try:
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "path": str(replay_path), "blockers": ("visual_replay_invalid_json",)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "path": str(replay_path), "blockers": ("visual_replay_not_object",)}

    state = payload.get("state", {})
    events = payload.get("events", ())
    metadata = payload.get("metadata", {})
    if payload.get("ok") is not True:
        blockers.append("visual_replay_not_ok")
    if payload.get("schema_version") != VISUAL_SCHEMA_VERSION:
        blockers.append("visual_replay_schema_mismatch")
    if payload.get("provenance") != "replay":
        blockers.append("visual_replay_provenance_not_replay")
    if not isinstance(events, list) or not events:
        blockers.append("visual_replay_events_missing")
    if not isinstance(state, Mapping):
        blockers.append("visual_replay_state_missing")
        state = {}
    if not state.get("agents"):
        blockers.append("visual_replay_agents_missing")
    if not state.get("tasks"):
        blockers.append("visual_replay_tasks_missing")
    if not state.get("economy"):
        blockers.append("visual_replay_economy_missing")
    if not any(str(event.get("provenance", "")) in {"live", "replay"} for event in events if isinstance(event, Mapping)):
        blockers.append("visual_replay_event_provenance_missing")

    return {
        "ok": not blockers,
        "path": str(replay_path),
        "schema_version": payload.get("schema_version"),
        "event_count": len(events) if isinstance(events, list) else 0,
        "agent_count": len(state.get("agents", ())) if isinstance(state, Mapping) else 0,
        "task_count": len(state.get("tasks", ())) if isinstance(state, Mapping) else 0,
        "economy_edge_count": len(state.get("economy", ())) if isinstance(state, Mapping) else 0,
        "metadata": dict(metadata) if isinstance(metadata, Mapping) else {},
        "blockers": tuple(blockers),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Mission Control visual replay artifact")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    result = validate_visual_replay(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
