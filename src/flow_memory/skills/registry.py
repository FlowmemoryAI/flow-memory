"""In-memory skill registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from flow_memory.safety.audit import ImmutableAuditLog
from flow_memory.skills.manifest import SkillManifest


@dataclass
class SkillRegistry:
    """Deterministic registry of skill manifests."""

    audit: ImmutableAuditLog | None = None
    _skills: dict[str, SkillManifest] = field(default_factory=dict, init=False, repr=False)

    def register(self, manifest: SkillManifest) -> SkillManifest:
        errors = manifest.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if manifest.skill_id in self._skills:
            raise ValueError(f"Skill already registered: {manifest.skill_id}")
        self._skills[manifest.skill_id] = manifest
        if self.audit is not None:
            self.audit.append({"kind": "skill_registered", "skill": manifest.as_record()})
        return manifest

    def get(self, skill_id: str) -> SkillManifest:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {skill_id}") from exc

    def list(self) -> tuple[SkillManifest, ...]:
        return tuple(self._skills[skill_id] for skill_id in sorted(self._skills))

    def manifests(self) -> tuple[SkillManifest, ...]:
        return self.list()

    def __contains__(self, skill_id: object) -> bool:
        return isinstance(skill_id, str) and skill_id in self._skills

    def __iter__(self) -> Iterable[SkillManifest]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self._skills)
