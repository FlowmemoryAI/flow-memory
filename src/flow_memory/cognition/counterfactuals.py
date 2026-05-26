"""Counterfactual prediction sets."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flow_memory.cognition.prediction import PredictionRecord
from flow_memory.cognition.state import stable_id


@dataclass(frozen=True)
class CounterfactualSet:
    counterfactual_id: str
    state_id: str
    goal: str
    candidate_predictions: tuple[PredictionRecord, ...]
    recommended_action_id: str
    rejected_action_ids: tuple[str, ...] = field(default_factory=tuple)
    selection_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "counterfactual_id": self.counterfactual_id,
            "state_id": self.state_id,
            "goal": self.goal,
            "candidate_predictions": tuple(prediction.as_record() for prediction in self.candidate_predictions),
            "recommended_action_id": self.recommended_action_id,
            "rejected_action_ids": self.rejected_action_ids,
            "selection_reason": self.selection_reason,
        }


def build_counterfactual_set(state_id: str, goal: str, predictions: tuple[PredictionRecord, ...]) -> CounterfactualSet:
    if not predictions:
        raise ValueError("at least one prediction is required")
    recommended = max(predictions, key=lambda item: item.expected_reward + item.confidence - item.risk)
    rejected = tuple(item.candidate_action_id for item in predictions if item.candidate_action_id != recommended.candidate_action_id)
    return CounterfactualSet(
        counterfactual_id=stable_id("counterfactual", state_id, *(item.prediction_id for item in predictions)),
        state_id=state_id,
        goal=goal,
        candidate_predictions=predictions,
        recommended_action_id=recommended.candidate_action_id,
        rejected_action_ids=rejected,
        selection_reason="selected highest expected reward plus confidence minus risk under policy constraints",
    )
