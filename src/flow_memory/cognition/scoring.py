"""Deterministic candidate scoring for predictive cognition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flow_memory.cognition.prediction import CandidateAction, PredictionRecord


@dataclass(frozen=True)
class CandidateScore:
    candidate_action_id: str
    goal_progress_score: float
    prediction_confidence: float
    risk_score: float
    cost_score: float
    policy_risk: float
    memory_support: float
    overall_score: float
    recommended: bool = False

    def as_record(self) -> dict[str, Any]:
        return dict(self.__dict__)


def score_candidate(action: CandidateAction, prediction: PredictionRecord, *, memory_support: float = 0.0) -> CandidateScore:
    policy_risk = 0.72 if action.requires_approval or action.policy_sensitive else 0.05
    cost_score = min(1.0, float(dict(action.estimated_cost).get("time_seconds", 30) or 30) / 300.0)
    goal_progress = max(0.0, min(1.0, prediction.expected_reward))
    overall = goal_progress * 0.34 + prediction.confidence * 0.28 + memory_support * 0.16 - prediction.risk * 0.14 - cost_score * 0.04 - policy_risk * 0.04
    return CandidateScore(
        candidate_action_id=action.action_id,
        goal_progress_score=round(goal_progress, 6),
        prediction_confidence=round(prediction.confidence, 6),
        risk_score=round(prediction.risk, 6),
        cost_score=round(cost_score, 6),
        policy_risk=round(policy_risk, 6),
        memory_support=round(memory_support, 6),
        overall_score=round(max(0.0, min(1.0, overall)), 6),
    )


def score_candidates(actions: tuple[CandidateAction, ...], predictions: tuple[PredictionRecord, ...], *, memory_support: float = 0.0) -> tuple[CandidateScore, ...]:
    by_id = {prediction.candidate_action_id: prediction for prediction in predictions}
    scores = [score_candidate(action, by_id[action.action_id], memory_support=memory_support) for action in actions if action.action_id in by_id]
    if not scores:
        return ()
    best_id = max(scores, key=lambda item: item.overall_score).candidate_action_id
    return tuple(CandidateScore(**{**score.as_record(), "recommended": score.candidate_action_id == best_id}) for score in scores)
