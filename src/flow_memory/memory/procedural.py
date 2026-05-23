"""Procedural memory: skill and behavior registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any


@dataclass(frozen=True)
class ProceduralSkill:
    """Skill metadata; executable handlers live behind the tool registry."""

    name: str
    description: str
    required_permission: str = "tool.invoke"
    version: str = "0.1.0"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class SkillLibrary:
    """Procedural memory for learned and declared behaviors."""

    _skills: dict[str, ProceduralSkill] = field(default_factory=dict, init=False, repr=False)

    def register(self, skill: ProceduralSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> ProceduralSkill | None:
        return self._skills.get(name)

    def list(self) -> tuple[ProceduralSkill, ...]:
        return tuple(self._skills.values())
