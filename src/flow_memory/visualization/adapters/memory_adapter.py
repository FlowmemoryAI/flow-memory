"""Memory-to-visual telemetry adapter."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def memory_records_to_visual_events(records: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    return tuple(
        visual_event("memory", str(record.get("record_id") or record.get("memory_id") or index), {
            "memory_id": record.get("record_id") or record.get("memory_id") or f"memory-{index}",
            "agent_id": record.get("agent_id", ""),
            "kind": record.get("kind", "episode"),
            "summary": record.get("text") or record.get("summary") or "memory update",
            "importance": record.get("importance", 0.0),
        }, provenance=provenance)
        for index, record in enumerate(records)
    )
