"""Neural telemetry adapter."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def neural_record_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    plan_scores = record.get("plan_scores", ())
    first_score = plan_scores[0] if isinstance(plan_scores, (list, tuple)) and plan_scores else {}
    risk_scores = record.get("risk_scores", {}) if isinstance(record.get("risk_scores", {}), Mapping) else {}
    live_step = record.get("live_step", {}) if isinstance(record.get("live_step", {}), Mapping) else {}
    source_agent = agent_id or str(record.get("agent_id", live_step.get("agent_id", "neural-agent")))
    return (visual_event("neural", source_agent, {
        "agent_id": source_agent,
        "backend": record.get("backend", live_step.get("backend", "none")),
        "status": record.get("status", live_step.get("status", "observed")),
        "plan_score": live_step.get("plan_score", dict(first_score).get("total_score", 0.0) if isinstance(first_score, Mapping) else 0.0),
        "risk_score": live_step.get("risk_score", risk_scores.get("failure_probability", risk_scores.get("unsafe_action_likelihood", 0.0))),
        "surprise_score": live_step.get("surprise_score", record.get("surprise_score", 0.0)),
        "session_id": record.get("session_id", live_step.get("session_id", "")),
        "phase": live_step.get("phase", ""),
        "prediction_confidence": live_step.get("prediction_confidence", 0.0),
        "uncertainty": live_step.get("uncertainty", 0.0),
        "learning_tick_count": live_step.get("learning_tick_count", 0),
        "memory_activation_count": live_step.get("memory_activation_count", 0),
        "action_state": live_step.get("action_state", ""),
        "policy_gate_state": live_step.get("policy_gate_state", ""),
    }, provenance=provenance),)
