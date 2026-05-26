"""Evaluation helpers for predictive learning trials."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TrialEvaluation:
    scenario_id: str
    trial: int
    selected_action_id: str
    selected_action_description: str
    match_score: float
    prediction_error: float
    confidence: float
    risk: float
    policy_allowed: bool
    policy_overrode: bool
    selected_action_policy_sensitive: bool
    lesson_reused: bool
    retrieved_memory_count: int
    lesson_ids: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return dict(self.__dict__)


def evaluate_trial(scenario_id: str, trial: int, tick: Mapping[str, Any]) -> Mapping[str, Any]:
    selected = dict(tick.get("selected_action", {})) if isinstance(tick.get("selected_action", {}), Mapping) else {}
    prediction = dict(tick.get("prediction", {})) if isinstance(tick.get("prediction", {}), Mapping) else {}
    error = dict(tick.get("prediction_error", {})) if isinstance(tick.get("prediction_error", {}), Mapping) else {}
    policy = dict(tick.get("policy_decision", {})) if isinstance(tick.get("policy_decision", {}), Mapping) else {}
    lesson_reuse = dict(tick.get("lesson_reuse", {})) if isinstance(tick.get("lesson_reuse", {}), Mapping) else {}
    evaluation = TrialEvaluation(
        scenario_id=scenario_id,
        trial=trial,
        selected_action_id=str(selected.get("action_id", "")),
        selected_action_description=str(selected.get("description", "")),
        match_score=float(error.get("match_score", 0.0) or 0.0),
        prediction_error=float(error.get("prediction_error", 0.0) or 0.0),
        confidence=float(prediction.get("confidence", 0.0) or 0.0),
        risk=float(prediction.get("risk", 0.0) or 0.0),
        policy_allowed=bool(policy.get("allowed", True)),
        policy_overrode=bool(policy.get("allowed", True)) is False,
        selected_action_policy_sensitive=bool(selected.get("policy_sensitive", False) or selected.get("requires_approval", False)),
        lesson_reused=bool(lesson_reuse.get("reused", False)),
        retrieved_memory_count=len(tick.get("retrieved_memories", ()) or ()),
        lesson_ids=tuple(str(item) for item in lesson_reuse.get("lesson_ids", ()) if str(item).strip()),
    )
    return evaluation.as_record()


def benchmark_passed(metrics: Mapping[str, Any]) -> bool:
    after_accuracy = _number(metrics.get("prediction_accuracy_after"), 0.0)
    before_accuracy = _number(metrics.get("prediction_accuracy_before"), 0.0)
    after_error = _number(metrics.get("prediction_error_mean_after"), 1.0)
    before_error = _number(metrics.get("prediction_error_mean_before"), 1.0)
    repeated_mistakes = _number(metrics.get("repeated_mistake_rate"), 1.0)
    return (
        after_accuracy >= before_accuracy
        and after_error <= before_error
        and int(metrics.get("consolidated_lesson_count", 0) or 0) > 0
        and repeated_mistakes < 1.0
    )


def _number(value: Any, default: float) -> float:
    try:
        if value is not None and value != "":
            return float(value)
    except (TypeError, ValueError):
        return default
    return default
