"""Neural-inspired skill routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SkillRouteScore:
    skill_id: str
    score: float
    reasons: tuple[str, ...]

    def as_record(self) -> Mapping[str, object]:
        return {"skill_id": self.skill_id, "score": self.score, "reasons": tuple(self.reasons)}


class TinySkillRouter:
    def rank_skills(self, goal: str, skills: Sequence[Mapping[str, object]], history: Mapping[str, float] | None = None, reputation: Mapping[str, float] | None = None) -> tuple[SkillRouteScore, ...]:
        history = history or {}
        reputation = reputation or {}
        tokens = set(goal.lower().replace("-", " ").split())
        scored: list[SkillRouteScore] = []
        for skill in skills:
            skill_id = str(skill.get("id", skill.get("skill_id", "skill")))
            description = str(skill.get("description", ""))
            capabilities = set(str(item).lower() for item in skill.get("capabilities", ())) if isinstance(skill.get("capabilities", ()), (list, tuple, set)) else set()
            match = len(tokens & (set(description.lower().split()) | capabilities)) / max(1, len(tokens))
            hist = history.get(skill_id, 0.5)
            rep = reputation.get(skill_id, 0.5)
            risk = float(skill.get("risk", skill.get("risk_score", 0.1)) or 0.1)
            cost = float(skill.get("cost", 0.0) or 0.0)
            score = max(0.0, match * 0.45 + hist * 0.25 + rep * 0.2 - risk * 0.15 - cost * 0.05)
            scored.append(SkillRouteScore(skill_id, score, ("capability_match", "history", "reputation", "risk")))
        return tuple(sorted(scored, key=lambda item: item.score, reverse=True))
