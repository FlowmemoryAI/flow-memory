"""FlowIR skill declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.ir.policy import PermissionSpec, RiskLevel


@dataclass(frozen=True)
class SkillSpec:
    """Language-neutral declaration for a callable skill."""

    id: str
    description: str = ""
    permissions: tuple[PermissionSpec, ...] = field(default_factory=tuple)
    risk_level: str = RiskLevel.LOW.value
    inputs_schema: Mapping[str, Any] = field(default_factory=dict)
    outputs_schema: Mapping[str, Any] = field(default_factory=dict)
    wasm_component: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.id.strip():
            errors.append("skill id is required")
        if self.risk_level not in RiskLevel.values():
            errors.append(f"unknown risk level for skill {self.id!r}: {self.risk_level}")
        for permission in self.permissions:
            errors.extend(permission.validate())
        return tuple(errors)

    def permission_names(self) -> tuple[str, ...]:
        return tuple(permission.name for permission in self.permissions)

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "permissions": tuple(permission.as_manifest() for permission in self.permissions),
            "risk_level": self.risk_level,
            "inputs_schema": dict(self.inputs_schema),
            "outputs_schema": dict(self.outputs_schema),
            "wasm_component": self.wasm_component,
            "metadata": dict(self.metadata),
        }
