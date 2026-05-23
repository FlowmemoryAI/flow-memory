"""Skill runtime manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class SkillRuntimeManager(BaseRuntimeManager):
    """Tracks scheduled and recently executed local skills."""

    name: str = "skills"
    scheduled_skills: set[str] = field(default_factory=set)
    executed_skills: list[str] = field(default_factory=list)

    def schedule(self, skill_id: str) -> None:
        if not skill_id:
            raise ValueError("skill_id is required")
        self.scheduled_skills.add(skill_id)

    def record_run(self, skill_id: str) -> None:
        self.executed_skills.append(skill_id)

    def summary(self) -> Mapping[str, object]:
        return {"scheduled": tuple(sorted(self.scheduled_skills)), "executed": tuple(self.executed_skills)}
