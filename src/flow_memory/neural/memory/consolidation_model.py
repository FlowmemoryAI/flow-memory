"""Tiny consolidation priority model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ConsolidationScore:
    relevance: float
    recency: float
    surprise: float
    economic_value: float
    safety_importance: float

    @property
    def priority(self) -> float:
        return min(1.0, self.relevance * 0.25 + self.recency * 0.15 + self.surprise * 0.2 + self.economic_value * 0.2 + self.safety_importance * 0.2)

    def as_record(self) -> Mapping[str, float]:
        return {"relevance": self.relevance, "recency": self.recency, "surprise": self.surprise, "economic_value": self.economic_value, "safety_importance": self.safety_importance, "priority": self.priority}


class TinyConsolidationModel:
    def score(self, item: Any, *, relevance: float = 0.5, recency: float = 0.5, surprise: float = 0.0) -> ConsolidationScore:
        text = repr(item).lower()
        economic = 1.0 if any(term in text for term in ("settlement", "escrow", "slashing", "reputation", "dispute")) else 0.1
        safety = 1.0 if any(term in text for term in ("unsafe", "blocked", "policy", "approval", "incident")) else 0.1
        return ConsolidationScore(relevance, recency, surprise, economic, safety)
