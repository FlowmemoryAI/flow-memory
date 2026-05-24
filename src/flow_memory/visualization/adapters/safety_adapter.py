"""Safety decision visual adapter."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def safety_record_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    return (visual_event("safety", str(record.get("decision_id") or record.get("gate_id") or "safety"), {
        "gate_id": record.get("decision_id") or record.get("gate_id") or "safety-gate",
        "agent_id": agent_id or record.get("agent_id", ""),
        "decision": "approved" if record.get("approved", record.get("ok", False)) else "blocked",
        "risk_level": record.get("risk_level", "low"),
        "requires_approval": record.get("requires_human", record.get("requires_approval", False)),
        "reason": "; ".join(str(item) for item in record.get("reasons", ())) if isinstance(record.get("reasons", ()), (list, tuple)) else str(record.get("reason", "")),
    }, provenance=provenance),)
