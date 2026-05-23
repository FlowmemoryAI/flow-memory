"""Skill quality evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from flow_memory.skills.runner import SkillRunResult


@dataclass(frozen=True)
class SkillEvaluation:
    skill_id: str
    score: float
    flags: Sequence[str] = field(default_factory=tuple)
    rationale: str = ""

    @property
    def passed(self) -> bool:
        return self.score >= 3.0 and "failed" not in self.flags


@dataclass
class SkillEvaluator:
    """Dependency-free scoring for local skill outputs."""

    min_output_chars: int = 12

    def evaluate(self, result: SkillRunResult) -> SkillEvaluation:
        flags: list[str] = []
        if not result.success:
            flags.append("failed")
            if result.error and "rate" in result.error.lower():
                flags.append("rate_limited")
            return SkillEvaluation(result.skill_id, 1.0, tuple(flags), result.error or "skill failed")

        output = result.output
        score = 3.0
        if _is_empty(output):
            return SkillEvaluation(result.skill_id, 1.0, ("empty_output",), "skill returned no useful output")
        if _char_count(output) >= self.min_output_chars:
            score += 1.0
        if _has_structure(output):
            score += 1.0
        return SkillEvaluation(result.skill_id, min(score, 5.0), tuple(flags), "local deterministic quality score")


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return len(value) == 0
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def _char_count(value: Any) -> int:
    return len(str(value))


def _has_structure(value: Any) -> bool:
    return isinstance(value, Mapping) and len(value) > 0
