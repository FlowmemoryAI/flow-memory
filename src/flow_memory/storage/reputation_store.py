"""Reputation persistence."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.storage.sqlite_store import SQLiteStore


class ReputationStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_update(self, update_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("reputation_updates", update_id, payload)

    def list_updates(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("reputation_updates")
