"""Prediction-error records and scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.cognition.prediction import PredictionRecord
from flow_memory.cognition.state import stable_id, utc_now


@dataclass(frozen=True)
class PredictionErrorRecord:
    error_id: str
    prediction_id: str
    actual_outcome_id: str
    match_score: float
    prediction_error: float
    error_type: str
    expected_fields: Mapping[str, Any] = field(default_factory=dict)
    actual_fields: Mapping[str, Any] = field(default_factory=dict)
    missing_expected: tuple[str, ...] = field(default_factory=tuple)
    unexpected_actual: tuple[str, ...] = field(default_factory=tuple)
    lesson: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "error_id": self.error_id,
            "prediction_id": self.prediction_id,
            "actual_outcome_id": self.actual_outcome_id,
            "match_score": self.match_score,
            "prediction_error": self.prediction_error,
            "error_type": self.error_type,
            "expected_fields": dict(self.expected_fields),
            "actual_fields": dict(self.actual_fields),
            "missing_expected": self.missing_expected,
            "unexpected_actual": self.unexpected_actual,
            "lesson": self.lesson,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "created_at": self.created_at,
        }


def compute_prediction_error(prediction: PredictionRecord | Mapping[str, Any], actual_outcome: Mapping[str, Any]) -> PredictionErrorRecord:
    pred = prediction.as_record() if isinstance(prediction, PredictionRecord) else dict(prediction)
    expected = dict(pred.get("predicted_state_patch", {}))
    actual = dict(actual_outcome.get("state_patch", actual_outcome))
    actual_id = str(actual_outcome.get("actual_outcome_id") or stable_id("actual_outcome", pred.get("prediction_id", ""), str(actual)))

    if expected:
        matches = sum(1 for key, value in expected.items() if actual.get(key) == value)
        missing = tuple(key for key in expected if key not in actual)
        mismatched = tuple(key for key, value in expected.items() if key in actual and actual.get(key) != value)
        match_score = matches / max(len(expected), 1)
        unexpected = tuple(key for key in actual if key not in expected)
        error_type = "exact_match" if match_score == 1.0 else "field_mismatch" if mismatched else "partial_match"
    else:
        predicted_success = float(pred.get("confidence", 0.5) or 0.5)
        actual_success = 1.0 if bool(actual_outcome.get("success", actual.get("success", False))) else 0.0
        match_score = max(0.0, 1.0 - abs(predicted_success - actual_success))
        missing = ()
        unexpected = tuple(actual.keys())
        error_type = "command_success_mismatch" if abs(predicted_success - actual_success) > 0.5 else "partial_match"

    if bool(actual_outcome.get("policy_denied", False)):
        error_type = "policy_denial_mismatch"
    if bool(actual_outcome.get("user_corrected", False)):
        error_type = "user_correction_mismatch"

    prediction_error = round(max(0.0, min(1.0, 1.0 - match_score)), 6)
    confidence_before = round(float(pred.get("confidence", 0.0) or 0.0), 6)
    confidence_after = round(max(0.0, min(1.0, confidence_before * (1.0 - prediction_error * 0.55) + (0.08 if prediction_error < 0.25 else -0.08))), 6)
    lesson = _lesson(pred, actual_outcome, prediction_error, error_type)
    return PredictionErrorRecord(
        error_id=stable_id("prediction_error", pred.get("prediction_id", ""), actual_id, error_type, prediction_error),
        prediction_id=str(pred.get("prediction_id", "")),
        actual_outcome_id=actual_id,
        match_score=round(match_score, 6),
        prediction_error=prediction_error,
        error_type=error_type,
        expected_fields=expected,
        actual_fields=actual,
        missing_expected=missing,
        unexpected_actual=unexpected,
        lesson=lesson,
        confidence_before=confidence_before,
        confidence_after=confidence_after,
    )


def _lesson(prediction: Mapping[str, Any], actual: Mapping[str, Any], error: float, error_type: str) -> str:
    action_id = str(prediction.get("candidate_action_id", "candidate action"))
    if error < 0.25:
        return f"Prediction matched the observed outcome for {action_id}; preserve this action pattern."
    if error_type == "policy_denial_mismatch":
        return "Policy denied the predicted action; future predictions must treat the policy gate as authoritative."
    if error_type == "user_correction_mismatch":
        return "User correction changed the outcome; store the correction as preference memory before acting again."
    reason = str(actual.get("reason") or actual.get("output") or error_type)
    return f"Prediction diverged for {action_id}: {reason}. Verify assumptions before repeating."
