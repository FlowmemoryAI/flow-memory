"""FlowIR memory declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class MemorySpec:
    """Memory configuration for a FlowIR agent."""

    working_capacity: int = 7
    episodic: bool = True
    semantic: bool = True
    procedural: bool = True
    economic: bool = False
    adapters: tuple[str, ...] = field(default_factory=lambda: ("local",))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.working_capacity < 1:
            errors.append("memory working_capacity must be at least 1")
        if any(not adapter.strip() for adapter in self.adapters):
            errors.append("memory adapters must be non-empty strings")
        return tuple(errors)

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "working_capacity": self.working_capacity,
            "episodic": self.episodic,
            "semantic": self.semantic,
            "procedural": self.procedural,
            "economic": self.economic,
            "adapters": tuple(self.adapters),
            "metadata": dict(self.metadata),
        }
