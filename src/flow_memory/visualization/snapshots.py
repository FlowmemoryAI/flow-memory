"""Snapshot helpers for Mission Control visual state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent
from flow_memory.visualization.reducer import reduce_visual_events
from flow_memory.visualization.state import VisualNetworkState


def build_visual_snapshot(events: Iterable[VisualEvent | Mapping[str, Any]], *, provenance: str = "live") -> Mapping[str, Any]:
    state = reduce_visual_events(events, provenance=provenance)
    return {"ok": True, "state": state.as_record(), "event_count": state.runtime.events}


def write_visual_snapshot(events: Iterable[VisualEvent | Mapping[str, Any]], path: str | Path, *, provenance: str = "replay") -> Mapping[str, Any]:
    snapshot = build_visual_snapshot(events, provenance=provenance)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return snapshot


def empty_visual_state() -> VisualNetworkState:
    return reduce_visual_events(())
