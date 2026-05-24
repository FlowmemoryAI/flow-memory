"""Neural telemetry adapter."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def neural_record_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    plan_scores = record.get("plan_scores", ())
    first_score = plan_scores[0] if isinstance(plan_scores, (list, tuple)) and plan_scores else {}
    risk_scores = record.get("risk_scores", {}) if isinstance(record.get("risk_scores", {}), Mapping) else {}
    return (visual_event("neural", agent_id or str(record.get("agent_id", "neural-agent")), {
        "agent_id": agent_id or record.get("agent_id", ""),
        "backend": record.get("backend", "none"),
        "status": record.get("status", "observed"),
        "plan_score": dict(first_score).get("total_score", 0.0) if isinstance(first_score, Mapping) else 0.0,
        "risk_score": risk_scores.get("failure_probability", risk_scores.get("unsafe_action_likelihood", 0.0)),
        "surprise_score": record.get("surprise_score", 0.0),
    }, provenance=provenance),)
