"""FlowIR policy contracts.

FlowIR is the language-neutral intermediate representation for Flow Memory
agents. It deliberately uses dataclasses and JSON-serializable primitives so it
can be emitted by FlowLang, loaded by Python, validated by Rust/Wasm hosts, and
reasoned over by Datalog policy engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class RiskLevel(str, Enum):
    """Canonical Flow Memory risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(level.value for level in cls)


_UNSAFE_PERMISSION_PREFIXES = (
    "chain.",
    "contracts.",
    "filesystem.write",
    "marketplace.bid",
    "marketplace.settle",
    "memory.write",
    "network.write",
    "shell.",
    "tool.exec",
    "wallet.",
)


@dataclass(frozen=True)
class PermissionSpec:
    """A single permission requested by an agent, skill, or plan step."""

    name: str
    description: str = ""
    requires_approval: bool = False

    def validate(self) -> tuple[str, ...]:
        if not self.name.strip():
            return ("permission name is required",)
        return ()

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class PolicySpec:
    """Policy declaration that can cover permissions and risk classes."""

    id: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = RiskLevel.LOW.value
    requires_approval: bool = False
    allow_unsafe: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.id.strip():
            errors.append("policy id is required")
        if self.risk_level not in RiskLevel.values():
            errors.append(f"unknown risk level for policy {self.id!r}: {self.risk_level}")
        if any(not permission.strip() for permission in self.permissions):
            errors.append(f"policy {self.id!r} contains an empty permission")
        return tuple(errors)

    def covers(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "permissions": tuple(self.permissions),
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "allow_unsafe": self.allow_unsafe,
            "metadata": dict(self.metadata),
        }


def is_unsafe_permission(permission: str) -> bool:
    """Return whether a permission can cause writes, external effects, or funds movement."""

    return any(permission == prefix or permission.startswith(prefix) for prefix in _UNSAFE_PERMISSION_PREFIXES)
