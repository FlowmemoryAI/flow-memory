"""Memory record persistence."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.storage.sqlite_store import SQLiteStore


class MemoryStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_record(self, record_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("memory_records", record_id, payload)

    def list_records(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("memory_records")
