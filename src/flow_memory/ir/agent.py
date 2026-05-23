"""FlowIR agent declaration."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any, Mapping

from flow_memory.ir.economy import EconomicSpec
from flow_memory.ir.memory import MemorySpec
from flow_memory.ir.plan import PlanSpec
from flow_memory.ir.policy import PolicySpec, is_unsafe_permission
from flow_memory.ir.skill import SkillSpec


@dataclass(frozen=True)
class AgentSpec:
    """Complete FlowIR declaration for a Flow Memory agent."""

    name: str
    identity: str = ""
    memory: MemorySpec = field(default_factory=MemorySpec)
    beliefs: tuple[str, ...] = field(default_factory=tuple)
    goals: tuple[str, ...] = field(default_factory=tuple)
    policies: tuple[PolicySpec, ...] = field(default_factory=tuple)
    skills: tuple[SkillSpec, ...] = field(default_factory=tuple)
    plans: tuple[PlanSpec, ...] = field(default_factory=tuple)
    economy: EconomicSpec = field(default_factory=EconomicSpec)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("agent name is required")
        errors.extend(self.memory.validate())
        errors.extend(self.economy.validate())

        for policy in self.policies:
            errors.extend(policy.validate())
        for skill in self.skills:
            errors.extend(skill.validate())
        for plan in self.plans:
            errors.extend(plan.validate())

        policy_ids = _duplicates(policy.id for policy in self.policies)
        skill_ids = _duplicates(skill.id for skill in self.skills)
        plan_ids = _duplicates(plan.id for plan in self.plans)
        for duplicate in policy_ids:
            errors.append(f"duplicate policy id: {duplicate}")
        for duplicate in skill_ids:
            errors.append(f"duplicate skill id: {duplicate}")
        for duplicate in plan_ids:
            errors.append(f"duplicate plan id: {duplicate}")

        policies = tuple(self.policies)
        for skill in self.skills:
            for permission in skill.permission_names():
                if is_unsafe_permission(permission) and not any(policy.covers(permission) for policy in policies):
                    errors.append(f"unsafe skill permission {permission!r} requires a policy")

        if self.economy.requires_identity() and not self.identity.strip():
            errors.append("economic settlement requires identity")

        skill_names = frozenset(skill.id for skill in self.skills)
        for plan in self.plans:
            for step in plan.steps:
                if step not in skill_names:
                    errors.append(f"plan {plan.id!r} references missing skill {step!r}")
        return tuple(errors)

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "identity": self.identity,
            "memory": self.memory.as_manifest(),
            "beliefs": tuple(self.beliefs),
            "goals": tuple(self.goals),
            "policies": tuple(policy.as_manifest() for policy in self.policies),
            "skills": tuple(skill.as_manifest() for skill in self.skills),
            "plans": tuple(plan.as_manifest() for plan in self.plans),
            "economy": self.economy.as_manifest(),
            "metadata": dict(self.metadata),
        }


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)
