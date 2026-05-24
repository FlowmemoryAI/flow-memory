"""Audit record visual adapter."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def audit_records_to_visual_events(records: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    events: list[VisualEvent] = []
    for index, record in enumerate(records):
        event_id = str(record.get("event_id") or record.get("receipt_id") or f"audit-{index}")
        events.append(visual_event("audit", str(record.get("actor") or record.get("principal") or record.get("source", "system")), {
            "audit_id": event_id,
            "event_type": record.get("event") or record.get("receipt_type") or record.get("method") or "audit",
            "actor_id": record.get("actor") or record.get("principal") or record.get("source", "system"),
            "summary": record.get("summary") or record.get("event") or record.get("receipt_type") or "audit event",
            "ok": record.get("ok", True),
        }, provenance=provenance, source_event_id=event_id))
    return tuple(events)
