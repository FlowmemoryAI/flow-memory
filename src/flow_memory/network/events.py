"""Network event helpers for visual replay and audit reports."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.visualization import VisualEvent
from flow_memory.visualization.adapters import agent_participants_to_visual_events, audit_records_to_visual_events


def topology_visual_events(topology_record: Mapping[str, Any], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    participants = topology_record.get("participants", ())
    if not isinstance(participants, Iterable):
        return ()
    return agent_participants_to_visual_events(tuple(item for item in participants if isinstance(item, Mapping)), provenance=provenance)


def audit_visual_events(records: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    return audit_records_to_visual_events(records, provenance=provenance)
