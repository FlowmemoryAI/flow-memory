"""Learning report records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentLearningReport:
    agent_id: str
    episodes: int
    success_rate: float
    average_reward: float
    safety_violations: int
    disputes: int
    memory_count: int
    policy_changes: int
    before_after: Mapping[str, Any]
    traces: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "agent_id": self.agent_id,
            "episodes": self.episodes,
            "success_rate": self.success_rate,
            "average_reward": self.average_reward,
            "safety_violations": self.safety_violations,
            "disputes": self.disputes,
            "memory_count": self.memory_count,
            "policy_changes": self.policy_changes,
            "before_after": dict(self.before_after),
            "traces": self.traces,
            "learning_modes": ("memory", "rl_arena", "neural_training_lane"),
            "prototype_limitations": "local traces and tiny RL/neural paths only; no production model training claim",
        }
