"""FlowIR plan declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.ir.policy import RiskLevel


@dataclass(frozen=True)
class PlanSpec:
    """A named plan that references declared skills by id."""

    id: str
    steps: tuple[str, ...] = field(default_factory=tuple)
    goal: str = ""
    risk_level: str = RiskLevel.LOW.value
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.id.strip():
            errors.append("plan id is required")
        if self.risk_level not in RiskLevel.values():
            errors.append(f"unknown risk level for plan {self.id!r}: {self.risk_level}")
        if any(not step.strip() for step in self.steps):
            errors.append(f"plan {self.id!r} contains an empty step")
        return tuple(errors)

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "steps": tuple(self.steps),
            "goal": self.goal,
            "risk_level": self.risk_level,
            "metadata": dict(self.metadata),
        }
