"""Visual replay import/export helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent
from flow_memory.visualization.snapshots import build_visual_snapshot


def load_visual_events(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, Mapping) and "visual_events" in payload:
        events = payload["visual_events"]
    elif isinstance(payload, Mapping) and "events" in payload:
        events = payload["events"]
    elif isinstance(payload, list):
        events = payload
    else:
        events = ()
    return tuple(dict(event) for event in events if isinstance(event, Mapping))


def replay_visual_events(path: str | Path) -> Mapping[str, Any]:
    return build_visual_snapshot(load_visual_events(path), provenance="replay")


def event_from_record(record: Mapping[str, Any]) -> VisualEvent:
    kwargs: dict[str, Any] = {
        "event_type": str(record.get("event_type", "unknown")),
        "source": str(record.get("source", "unknown")),
        "payload": dict(record.get("payload", {})) if isinstance(record.get("payload", {}), Mapping) else {},
        "provenance": str(record.get("provenance", "replay")),
        "source_event_id": str(record.get("source_event_id", "")),
    }
    if record.get("event_id"):
        kwargs["event_id"] = str(record["event_id"])
    if record.get("created_at"):
        kwargs["created_at"] = str(record["created_at"])
    return VisualEvent(**kwargs)
