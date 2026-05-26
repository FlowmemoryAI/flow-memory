"""Visual telemetry for predictive cognition."""
from __future__ import annotations

from typing import Mapping

from flow_memory.visualization.events import VisualEvent, visual_event

COGNITION_EVENT_TYPES = (
    "cognition_state_encoded",
    "cognition_memory_retrieved",
    "cognition_candidate_actions_generated",
    "cognition_prediction_generated",
    "cognition_counterfactuals_generated",
    "cognition_candidate_scored",
    "cognition_action_selected",
    "cognition_policy_gate_applied",
    "cognition_actual_outcome_observed",
    "cognition_prediction_error_computed",
    "cognition_experience_written",
    "cognition_lesson_learned",
    "cognition_learning_update_completed",
)


def cognition_tick_to_visual_events(tick: Mapping[str, object], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    agent_id = str(dict(tick.get("state", {})).get("agent_id", "cognition-agent")) if isinstance(tick.get("state"), Mapping) else "cognition-agent"
    events = []
    for event_name in COGNITION_EVENT_TYPES:
        events.append(visual_event("cognitive", agent_id, _payload_for(event_name, tick, agent_id), provenance=provenance))
    return tuple(events)


def _payload_for(event_name: str, tick: Mapping[str, object], agent_id: str) -> Mapping[str, object]:
    prediction = dict(tick.get("prediction", {})) if isinstance(tick.get("prediction"), Mapping) else {}
    error = dict(tick.get("prediction_error", {})) if isinstance(tick.get("prediction_error"), Mapping) else {}
    experience = dict(tick.get("experience", {})) if isinstance(tick.get("experience"), Mapping) else {}
    return {
        "agent_id": agent_id,
        "event": event_name,
        "prediction_id": prediction.get("prediction_id", ""),
        "experience_id": experience.get("experience_id", ""),
        "goal": prediction.get("goal", dict(tick.get("state", {})).get("goal", "") if isinstance(tick.get("state"), Mapping) else ""),
        "chosen_action": dict(tick.get("selected_action", {})).get("description", "") if isinstance(tick.get("selected_action"), Mapping) else "",
        "predicted_outcome": prediction.get("predicted_result", ""),
        "actual_result": tick.get("actual_outcome", {}),
        "actual_summary": _actual_summary(dict(tick.get("actual_outcome", {})) if isinstance(tick.get("actual_outcome"), Mapping) else {}),
        "confidence": prediction.get("confidence", 0.0),
        "prediction_error": error.get("prediction_error", 0.0),
        "success": bool(dict(tick.get("actual_outcome", {})).get("success", False)) if isinstance(tick.get("actual_outcome"), Mapping) else False,
        "lesson": error.get("lesson", experience.get("lesson", "")),
        "future_policy": experience.get("lesson", ""),
    }


def _actual_summary(actual: Mapping[str, object]) -> str:
    if actual.get("reason"):
        return str(actual.get("reason"))
    if actual.get("simulated"):
        return "simulated local outcome"
    return "success" if actual.get("success") else "observed"
