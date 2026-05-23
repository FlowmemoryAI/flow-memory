"""Local pricing heuristics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingQuote:
    base_reward: float
    complexity_multiplier: float
    risk_multiplier: float

    @property
    def suggested_reward(self) -> float:
        return round(max(0.0, self.base_reward * self.complexity_multiplier * self.risk_multiplier), 6)


@dataclass
class PricingHeuristic:
    """Dependency-free pricing for local marketplace tasks."""

    base_reward: float = 1.0

    def quote(self, complexity: float = 1.0, risk_level: str = "low") -> PricingQuote:
        risk_multiplier = {"low": 1.0, "medium": 1.5, "high": 2.5, "critical": 4.0}.get(risk_level, 1.5)
        return PricingQuote(self.base_reward, max(0.1, complexity), risk_multiplier)
