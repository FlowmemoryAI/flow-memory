"""Deterministic neural-inspired plan scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PlanScore:
    plan_id: str
    expected_success: float
    expected_cost: float
    policy_risk: float
    economic_risk: float
    memory_similarity: float

    @property
    def total_score(self) -> float:
        return max(0.0, self.expected_success + self.memory_similarity * 0.2 - self.policy_risk * 0.35 - self.economic_risk * 0.25 - self.expected_cost * 0.1)

    def as_record(self) -> Mapping[str, float | str]:
        return {"plan_id": self.plan_id, "expected_success": self.expected_success, "expected_cost": self.expected_cost, "policy_risk": self.policy_risk, "economic_risk": self.economic_risk, "memory_similarity": self.memory_similarity, "total_score": self.total_score}


class TinyPlanScorer:
    def score_plan(self, plan: Any, successful_memory_similarity: float = 0.0) -> PlanScore:
        risk_order = {"low": 0.1, "medium": 0.35, "high": 0.7, "critical": 1.0}
        risk_level = getattr(plan, "risk_level", "low")
        plan_id = getattr(plan, "plan_id", getattr(plan, "id", "plan"))
        economic_value = float(getattr(plan, "economic_value", 0.0))
        steps = tuple(getattr(plan, "steps", ()))
        expected_success = max(0.0, 0.95 - 0.03 * max(0, len(steps) - 1) - risk_order.get(risk_level, 0.5) * 0.25)
        return PlanScore(str(plan_id), expected_success, float(len(steps)) * 0.1 + economic_value * 0.05, risk_order.get(risk_level, 0.5), min(1.0, economic_value / 10.0), successful_memory_similarity)

    def rank(self, plans: Sequence[Any]) -> tuple[PlanScore, ...]:
        return tuple(sorted((self.score_plan(plan) for plan in plans), key=lambda score: score.total_score, reverse=True))
