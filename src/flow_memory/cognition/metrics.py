"""Metrics for deterministic predictive learning benchmarks."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.cognition.experience import list_experiences
from flow_memory.cognition.consolidation import list_lessons


def prediction_accuracy(trials: Iterable[Mapping[str, Any]]) -> float:
    records = tuple(trials)
    return _round(_mean(float(record.get("match_score", 0.0) or 0.0) for record in records))


def prediction_error_mean(trials: Iterable[Mapping[str, Any]]) -> float:
    records = tuple(trials)
    return _round(_mean(float(record.get("prediction_error", 0.0) or 0.0) for record in records))


def confidence_calibration(trials: Iterable[Mapping[str, Any]]) -> float:
    records = tuple(trials)
    if not records:
        return 0.0
    error = _mean(abs(float(record.get("confidence", 0.0) or 0.0) - float(record.get("match_score", 0.0) or 0.0)) for record in records)
    return _round(max(0.0, min(1.0, 1.0 - error)))


def learning_metrics(
    trials: Iterable[Mapping[str, Any]],
    *,
    consolidated_lesson_count: int = 0,
) -> Mapping[str, Any]:
    records = tuple(trials)
    first_trials, last_trials = _first_last_by_scenario(records)
    before_accuracy = prediction_accuracy(first_trials)
    after_accuracy = prediction_accuracy(last_trials)
    before_error = prediction_error_mean(first_trials)
    after_error = prediction_error_mean(last_trials)
    count = len(records)
    unsafe_count = sum(1 for record in records if int(record.get("trial", 0) or 0) > 1 and record.get("selected_action_policy_sensitive") is True)
    override_count = sum(1 for record in records if record.get("policy_allowed") is False)
    lesson_reuse_count = sum(1 for record in records if record.get("lesson_reused") is True)
    retrieval_hit_count = sum(1 for record in records if int(record.get("retrieved_memory_count", 0) or 0) > 0)
    high_error_after_first = sum(1 for record in records if int(record.get("trial", 0) or 0) > 1 and float(record.get("prediction_error", 0.0) or 0.0) >= 0.5)
    after_first_count = sum(1 for record in records if int(record.get("trial", 0) or 0) > 1)
    return {
        "prediction_accuracy_before": before_accuracy,
        "prediction_accuracy_after": after_accuracy,
        "prediction_accuracy_delta": _round(after_accuracy - before_accuracy),
        "prediction_error_mean_before": before_error,
        "prediction_error_mean_after": after_error,
        "prediction_error_delta": _round(before_error - after_error),
        "confidence_calibration": confidence_calibration(records),
        "memory_retrieval_hit_rate": _rate(retrieval_hit_count, count),
        "lesson_reuse_rate": _rate(lesson_reuse_count, count),
        "unsafe_recommendation_rate": _rate(unsafe_count, after_first_count),
        "policy_override_rate": _rate(override_count, count),
        "repeated_mistake_rate": _rate(high_error_after_first, after_first_count),
        "time_to_resolution_proxy": _time_to_resolution(records),
        "experience_count": count,
        "consolidated_lesson_count": int(consolidated_lesson_count),
    }


def cognition_metrics(root: str = ".") -> Mapping[str, Any]:
    experiences = tuple(list_experiences(root))
    lessons = tuple(list_lessons(root))
    trial_like = tuple(_trial_from_experience(record) for record in experiences)
    metrics = learning_metrics(trial_like, consolidated_lesson_count=len(lessons)) if trial_like else {
        "prediction_accuracy_before": 0.0,
        "prediction_accuracy_after": 0.0,
        "prediction_accuracy_delta": 0.0,
        "prediction_error_mean_before": 0.0,
        "prediction_error_mean_after": 0.0,
        "prediction_error_delta": 0.0,
        "confidence_calibration": 0.0,
        "memory_retrieval_hit_rate": 0.0,
        "lesson_reuse_rate": 0.0,
        "unsafe_recommendation_rate": 0.0,
        "policy_override_rate": 0.0,
        "repeated_mistake_rate": 0.0,
        "time_to_resolution_proxy": 0,
        "experience_count": 0,
        "consolidated_lesson_count": len(lessons),
    }
    return {
        "ok": True,
        **metrics,
        "experience_count": len(experiences),
        "consolidated_lesson_count": len(lessons),
        "local_only": True,
    }


def _trial_from_experience(record: Mapping[str, Any]) -> Mapping[str, Any]:
    error = dict(record.get("prediction_error", {})) if isinstance(record.get("prediction_error", {}), Mapping) else {}
    prediction = dict(record.get("prediction", {})) if isinstance(record.get("prediction", {}), Mapping) else {}
    selected = dict(record.get("selected_action", {})) if isinstance(record.get("selected_action", {}), Mapping) else {}
    policy = dict(record.get("policy_decision", {})) if isinstance(record.get("policy_decision", {}), Mapping) else {}
    return {
        "scenario_id": tuple(record.get("memory_tags", ("general",)))[-1] if record.get("memory_tags") else "general",
        "trial": 1,
        "match_score": float(error.get("match_score", 0.0) or 0.0),
        "prediction_error": float(error.get("prediction_error", 0.0) or 0.0),
        "confidence": float(prediction.get("confidence", 0.0) or 0.0),
        "retrieved_memory_count": len(record.get("retrieved_memory_ids", ()) or ()),
        "lesson_reused": bool(record.get("lesson_reused", False)),
        "selected_action_policy_sensitive": bool(selected.get("policy_sensitive", False)),
        "policy_allowed": bool(policy.get("allowed", True)),
    }


def _first_last_by_scenario(records: tuple[Mapping[str, Any], ...]) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("scenario_id", "default")), []).append(record)
    first = []
    last = []
    for values in grouped.values():
        ordered = sorted(values, key=lambda item: int(item.get("trial", 0) or 0))
        if ordered:
            first.append(ordered[0])
            last.append(ordered[-1])
    return tuple(first), tuple(last)


def _time_to_resolution(records: tuple[Mapping[str, Any], ...]) -> int:
    resolved = [int(record.get("trial", 0) or 0) for record in records if float(record.get("match_score", 0.0) or 0.0) >= 0.75]
    return min(resolved) if resolved else len(records)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round(numerator / denominator)


def _mean(values: Iterable[float]) -> float:
    numbers = tuple(values)
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def _round(value: float) -> float:
    return round(float(value), 6)
