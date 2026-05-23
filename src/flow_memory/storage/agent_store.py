"""Agent profile/state persistence."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.storage.sqlite_store import SQLiteStore


class AgentStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_profile(self, agent_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("agents", agent_id, payload)

    def load_profile(self, agent_id: str) -> Mapping[str, Any] | None:
        return self.store.get("agents", agent_id)

    def save_state(self, agent_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("agent_state", agent_id, payload)

    def load_state(self, agent_id: str) -> Mapping[str, Any] | None:
        return self.store.get("agent_state", agent_id)
