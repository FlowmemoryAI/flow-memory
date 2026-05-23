"""Agent self-reflection and repair recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.agents.evaluator import AgentEvaluation


@dataclass(frozen=True)
class ReflectionReport:
    critique: str
    repair_recommendation: str
    consolidate_memory: bool
    skill_improvement: str = ""
    safety_incident: bool = False

    def as_record(self) -> Mapping[str, Any]:
        return {
            "critique": self.critique,
            "repair_recommendation": self.repair_recommendation,
            "consolidate_memory": self.consolidate_memory,
            "skill_improvement": self.skill_improvement,
            "safety_incident": self.safety_incident,
        }


class AgentReflector:
    def reflect(self, evaluation: AgentEvaluation) -> ReflectionReport:
        if evaluation.safety_incident:
            return ReflectionReport("Safety incident detected", "pause agent and require human review", True, safety_incident=True)
        if not evaluation.success:
            return ReflectionReport("Execution failed", "generate repair plan and retry only after policy approval", True, "review failed skill")
        if evaluation.quality_score < 0.7:
            return ReflectionReport("Output quality below target", "add context and improve skill prompt/implementation", True, "improve output scoring")
        return ReflectionReport("Execution met local criteria", "no repair required", evaluation.quality_score > 0.85)
