"""Versioned visual event records for Mission Control."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id

VISUAL_SCHEMA_VERSION = "visual.telemetry.v1"
VALID_PROVENANCE = frozenset({"live", "replay", "mock", "synthetic"})


@dataclass(frozen=True)
class VisualEvent:
    """Small JSON-serializable event consumed by Mission Control."""

    event_type: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    provenance: str = "live"
    source_event_id: str = ""
    event_id: str = field(default_factory=lambda: new_id("visual_event"))
    schema_version: str = VISUAL_SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.provenance not in VALID_PROVENANCE:
            raise ValueError(f"invalid visual event provenance: {self.provenance}")
        if not self.event_type:
            raise ValueError("visual event_type is required")
        if not self.source:
            raise ValueError("visual event source is required")

    def as_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "source_event_id": self.source_event_id,
            "provenance": self.provenance,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


def visual_event(event_type: str, source: str, payload: Mapping[str, Any] | None = None, *, provenance: str = "live", source_event_id: str = "") -> VisualEvent:
    return VisualEvent(event_type=event_type, source=source, payload=dict(payload or {}), provenance=provenance, source_event_id=source_event_id)
