"""Machine-readable Mission Control visual schema."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION


def visual_schema() -> Mapping[str, Any]:
    return {
        "schema_version": VISUAL_SCHEMA_VERSION,
        "provenance_values": ("live", "replay", "mock", "synthetic"),
        "event_types": ("agent", "task", "memory", "economy", "neural", "rl", "safety", "audit"),
        "state_collections": ("agents", "tasks", "memory", "economy", "neural", "rl", "safety", "audit"),
        "required_reference": "source_event_id when available",
    }
