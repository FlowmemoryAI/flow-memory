"""Typed cognitive planner for Flow Memory agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class PlanStep:
    action: str
    required_tools: tuple[str, ...] = field(default_factory=tuple)
    required_skills: tuple[str, ...] = field(default_factory=tuple)
    required_permissions: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"
    expected_outputs: tuple[str, ...] = field(default_factory=tuple)
    economic_value: float = 0.0
    step_id: str = field(default_factory=lambda: new_id("plan_step"))

    def as_record(self) -> Mapping[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "required_tools": tuple(self.required_tools),
            "required_skills": tuple(self.required_skills),
            "required_permissions": tuple(self.required_permissions),
            "risk_level": self.risk_level,
            "expected_outputs": tuple(self.expected_outputs),
            "economic_value": self.economic_value,
        }


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple[PlanStep, ...]
    success_criteria: tuple[str, ...] = field(default_factory=tuple)
    rollback_strategy: str = "stop and preserve audit trail"
    economic_intent: bool = False
    plan_id: str = field(default_factory=lambda: new_id("agent_plan"))

    @property
    def risk_level(self) -> str:
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return max((step.risk_level for step in self.steps), key=lambda level: order.get(level, 3), default="low")

    @property
    def economic_value(self) -> float:
        return sum(step.economic_value for step in self.steps)

    @property
    def required_permissions(self) -> tuple[str, ...]:
        permissions: list[str] = []
        for step in self.steps:
            permissions.extend(step.required_permissions)
        return tuple(dict.fromkeys(permissions))

    def as_record(self) -> Mapping[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": tuple(step.as_record() for step in self.steps),
            "risk_level": self.risk_level,
            "success_criteria": tuple(self.success_criteria),
            "rollback_strategy": self.rollback_strategy,
            "economic_intent": self.economic_intent,
            "economic_value": self.economic_value,
        }


class CognitivePlanner:
    def create_plan(self, goal: str, *, allowed_skills: tuple[str, ...] = (), allowed_tools: tuple[str, ...] = ()) -> Plan:
        lowered = goal.lower()
        economic = any(term in lowered for term in ("settle", "marketplace", "bid", "escrow", "pay"))
        if economic:
            skill = allowed_skills[0] if allowed_skills else "economic-task"
            steps = (
                PlanStep(
                    action="run_skill",
                    required_skills=(skill,),
                    required_permissions=("marketplace.settle",),
                    risk_level="high",
                    expected_outputs=("settlement_receipt",),
                    economic_value=1.0,
                ),
            )
        elif allowed_skills:
            steps = (
                PlanStep(
                    action="run_skill",
                    required_skills=(allowed_skills[0],),
                    required_permissions=("memory.read", "audit.emit"),
                    risk_level="low",
                    expected_outputs=("skill_output",),
                ),
            )
        else:
            tool = allowed_tools[0] if allowed_tools else "respond"
            steps = (
                PlanStep(
                    action="respond",
                    required_tools=(tool,),
                    required_permissions=("respond",),
                    risk_level="low",
                    expected_outputs=("response",),
                ),
            )
        return Plan(goal=goal, steps=steps, success_criteria=("produce auditable result",), economic_intent=economic)
