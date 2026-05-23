"""FlowIR economic declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EconomicSpec:
    """Local-first economic settings for an agent."""

    settlement: str = "none"
    budget: float = 0.0
    currency: str = "LOCAL"
    marketplace: str = "local"
    allow_slashing: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.budget < 0:
            errors.append("economic budget must be non-negative")
        if self.settlement not in {"none", "local", "base-sepolia", "base"}:
            errors.append(f"unknown settlement mode: {self.settlement}")
        if not self.currency.strip():
            errors.append("economic currency is required")
        return tuple(errors)

    def requires_identity(self) -> bool:
        return self.settlement != "none" or self.budget > 0 or self.allow_slashing

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "settlement": self.settlement,
            "budget": self.budget,
            "currency": self.currency,
            "marketplace": self.marketplace,
            "allow_slashing": self.allow_slashing,
            "metadata": dict(self.metadata),
        }
