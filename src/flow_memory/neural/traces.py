"""Agent trace dataclasses used by neural datasets and evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class PlanTrace:
    goal: str
    plan_steps: tuple[str, ...]
    success: bool
    cost: float = 0.0
    risk: float = 0.0

    def as_record(self) -> Mapping[str, Any]:
        return {"goal": self.goal, "plan_steps": tuple(self.plan_steps), "success": self.success, "cost": self.cost, "risk": self.risk}


@dataclass(frozen=True)
class SkillTrace:
    skill_id: str
    success: bool
    quality_score: float
    risk_score: float = 0.0

    def as_record(self) -> Mapping[str, Any]:
        return {"skill_id": self.skill_id, "success": self.success, "quality_score": self.quality_score, "risk_score": self.risk_score}


@dataclass(frozen=True)
class EconomyTrace:
    task_id: str
    settlement: str
    value: float
    dispute: bool = False
    slashed: bool = False

    def as_record(self) -> Mapping[str, Any]:
        return {"task_id": self.task_id, "settlement": self.settlement, "value": self.value, "dispute": self.dispute, "slashed": self.slashed}


@dataclass(frozen=True)
class AgentTrace:
    agent_id: str
    state_summary: str
    goal: str
    plan: PlanTrace
    skills: tuple[SkillTrace, ...] = field(default_factory=tuple)
    policy_decisions: tuple[str, ...] = field(default_factory=tuple)
    economy_receipts: tuple[EconomyTrace, ...] = field(default_factory=tuple)
    memory_writes: tuple[str, ...] = field(default_factory=tuple)
    final_quality_score: float = 0.0

    def as_record(self) -> Mapping[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state_summary": self.state_summary,
            "goal": self.goal,
            "plan": self.plan.as_record(),
            "skills": tuple(skill.as_record() for skill in self.skills),
            "policy_decisions": tuple(self.policy_decisions),
            "economy_receipts": tuple(receipt.as_record() for receipt in self.economy_receipts),
            "memory_writes": tuple(self.memory_writes),
            "final_quality_score": self.final_quality_score,
        }
