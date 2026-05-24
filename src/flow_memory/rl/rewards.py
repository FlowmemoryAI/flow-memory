"""Reward specification for Flow Arena."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class RewardSpec:
    task_success: float = 1.0
    safety_compliance: float = 1.0
    policy_violation_penalty: float = -2.0
    reputation_gain: float = 0.5
    dispute_penalty: float = -1.0
    slashing_penalty: float = -3.0
    memory_usefulness: float = 0.25
    delegation_success: float = 0.5
    def score(self, signals: Mapping[str, float|bool]) -> float:
        total=0.0
        for key, weight in self.as_record().items():
            value=signals.get(key, 0.0)
            total += float(value) * float(weight)
        return total
    def as_record(self):
        return {"task_success":self.task_success,"safety_compliance":self.safety_compliance,"policy_violation_penalty":self.policy_violation_penalty,"reputation_gain":self.reputation_gain,"dispute_penalty":self.dispute_penalty,"slashing_penalty":self.slashing_penalty,"memory_usefulness":self.memory_usefulness,"delegation_success":self.delegation_success}
