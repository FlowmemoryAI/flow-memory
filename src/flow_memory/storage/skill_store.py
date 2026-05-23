"""Skill manifest persistence."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.storage.sqlite_store import SQLiteStore


class SkillStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_skill(self, skill_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("skills", skill_id, payload)

    def list_skills(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("skills")
