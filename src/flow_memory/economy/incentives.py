"""Local incentive calculations."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncentivePolicy:
    quality_bonus: float = 0.1
    verifier_bonus: float = 0.05
    failure_penalty: float = 0.2

    def reward_for_quality(self, reward: float, quality_score: float) -> float:
        if quality_score >= 4.0:
            return round(reward * (1.0 + self.quality_bonus), 6)
        if quality_score < 2.0:
            return round(reward * (1.0 - self.failure_penalty), 6)
        return reward

    def verifier_reward(self, reward: float) -> float:
        return round(max(0.0, reward * self.verifier_bonus), 6)
