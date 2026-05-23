"""Learning update hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import ActionResult, Evaluation, Plan


@dataclass
class OnlineLearner:
    """Records update signals for model/memory/skill training loops."""

    updates: list[Mapping[str, Any]] = field(default_factory=list)
    surprise_threshold: float = 0.5

    def update(self, evaluation: Evaluation, plan: Plan, result: ActionResult) -> Mapping[str, Any]:
        update = {
            "plan_id": plan.plan_id,
            "success": result.success,
            "surprise_score": evaluation.surprise_score,
            "requires_consolidation": evaluation.surprise_score >= self.surprise_threshold,
            "step_count": len(plan.steps),
        }
        self.updates.append(update)
        return update
