"""Agent result evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentEvaluation:
    quality_score: float
    surprise_score: float
    success: bool
    safety_incident: bool = False
    notes: str = ""

    def as_record(self) -> Mapping[str, Any]:
        return {
            "quality_score": self.quality_score,
            "surprise_score": self.surprise_score,
            "success": self.success,
            "safety_incident": self.safety_incident,
            "notes": self.notes,
        }


class AgentEvaluator:
    def evaluate(self, output: Mapping[str, Any], *, expected: tuple[str, ...] = ()) -> AgentEvaluation:
        success = bool(output.get("success", True)) and not output.get("blocked")
        text = str(output.get("output", output))
        quality = min(1.0, 0.4 + len(text.strip()) / 200.0)
        if expected and any(term in text for term in expected):
            quality = min(1.0, quality + 0.2)
        surprise = 0.0 if success else 1.0
        return AgentEvaluation(quality_score=round(quality, 3), surprise_score=surprise, success=success, safety_incident=bool(output.get("safety_incident", False)))
