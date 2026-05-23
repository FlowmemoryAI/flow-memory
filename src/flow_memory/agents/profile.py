"""First-class Flow Memory agent profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class RiskBudget:
    max_risk_level: str = "medium"
    max_spend: float = 0.0
    max_escrow_exposure: float = 0.0
    max_slashing_exposure: float = 0.0

    def as_record(self) -> Mapping[str, Any]:
        return {
            "max_risk_level": self.max_risk_level,
            "max_spend": self.max_spend,
            "max_escrow_exposure": self.max_escrow_exposure,
            "max_slashing_exposure": self.max_slashing_exposure,
        }


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str = field(default_factory=lambda: new_id("agent"))
    name: str = "agent"
    identity: str = ""
    description: str = ""
    persona: str = ""
    goals: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    allowed_skills: tuple[str, ...] = field(default_factory=tuple)
    memory_config: Mapping[str, Any] = field(default_factory=dict)
    economy_config: Mapping[str, Any] = field(default_factory=dict)
    autonomy_mode: str = "supervised"
    risk_budget: RiskBudget = field(default_factory=RiskBudget)
    reputation: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("agent name is required")
        if self.autonomy_mode not in {"manual", "supervised", "autonomous_local", "autonomous_economic", "disabled"}:
            errors.append(f"unknown autonomy mode: {self.autonomy_mode}")
        if self.risk_budget.max_spend < 0:
            errors.append("risk budget max_spend must be non-negative")
        return tuple(errors)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "identity": self.identity,
            "description": self.description,
            "persona": self.persona,
            "goals": tuple(self.goals),
            "constraints": tuple(self.constraints),
            "capabilities": tuple(self.capabilities),
            "allowed_tools": tuple(self.allowed_tools),
            "allowed_skills": tuple(self.allowed_skills),
            "memory_config": dict(self.memory_config),
            "economy_config": dict(self.economy_config),
            "autonomy_mode": self.autonomy_mode,
            "risk_budget": self.risk_budget.as_record(),
            "reputation": self.reputation,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
