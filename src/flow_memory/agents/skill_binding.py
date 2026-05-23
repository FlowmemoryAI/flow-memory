"""Agent skill binding."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.skills import SkillManifest, SkillRegistry


class AgentSkillBinding:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()

    def ensure_skill(self, skill_id: str) -> None:
        try:
            self.registry.get(skill_id)
        except KeyError:
            self.registry.register(SkillManifest(id=skill_id, name=skill_id.replace("-", " ").title(), description="FlowLang declared skill"))

    def run_skill(self, skill_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.ensure_skill(skill_id)
        return {"success": True, "skill_id": skill_id, "output": dict(payload)}
