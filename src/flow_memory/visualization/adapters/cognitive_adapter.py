"""Predictive cognitive telemetry adapter."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def prediction_experience_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    prediction = dict(record.get("prediction", {})) if isinstance(record.get("prediction", {}), Mapping) else {}
    actual = dict(record.get("actual_result", {})) if isinstance(record.get("actual_result", {}), Mapping) else {}
    source_agent = agent_id or str(record.get("agent_id") or prediction.get("agent_id") or actual.get("agent_id") or "agent")
    prediction_id = str(record.get("prediction_id") or prediction.get("prediction_id") or record.get("experience_id", "prediction"))
    return (visual_event("cognitive", source_agent, {
        "agent_id": source_agent,
        "prediction_id": prediction_id,
        "experience_id": record.get("experience_id", ""),
        "goal": record.get("goal") or prediction.get("goal", ""),
        "chosen_action": record.get("chosen_action") or prediction.get("chosen_action", ""),
        "predicted_outcome": record.get("predicted_outcome") or prediction.get("predicted_outcome", ""),
        "actual_result": actual,
        "actual_summary": _actual_summary(actual),
        "confidence": record.get("confidence_before", prediction.get("confidence", 0.0)),
        "prediction_error": record.get("prediction_error", 0.0),
        "success": record.get("success", False),
        "lesson": record.get("lesson", ""),
        "future_policy": record.get("future_policy", ""),
    }, provenance=provenance),)


def _actual_summary(actual: Mapping[str, Any]) -> str:
    if "reason" in actual:
        return str(actual.get("reason"))
    if "output" in actual:
        return str(actual.get("output"))[:160]
    if "success" in actual:
        return "success" if bool(actual.get("success")) else "failed"
    return "observed"
