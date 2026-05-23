"""Safety-gated skill repair planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from flow_memory.skills.evaluator import SkillEvaluation


@dataclass(frozen=True)
class SkillRepairPlan:
    skill_id: str
    reason: str
    recommended_actions: Sequence[str]
    requires_approval: bool = True
    risk_level: str = "medium"
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass
class SkillRepairPlanner:
    """Creates repair plans but never applies code changes."""

    failure_threshold: float = 3.0

    def plan(self, evaluation: SkillEvaluation) -> SkillRepairPlan | None:
        if evaluation.score >= self.failure_threshold and not evaluation.flags:
            return None
        actions = [
            "inspect skill manifest and provenance",
            "re-run focused deterministic test",
            "adjust prompt/handler only after approval",
        ]
        risk = "high" if "unsafe_action" in evaluation.flags else "medium"
        return SkillRepairPlan(
            skill_id=evaluation.skill_id,
            reason=evaluation.rationale or ", ".join(evaluation.flags) or "quality below threshold",
            recommended_actions=tuple(actions),
            requires_approval=True,
            risk_level=risk,
            metadata={"flags": tuple(evaluation.flags), "score": evaluation.score},
        )
