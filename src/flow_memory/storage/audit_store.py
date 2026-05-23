"""Audit event store."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.core.types import new_id
from flow_memory.storage.sqlite_store import SQLiteStore


class AuditStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def append(self, event: Mapping[str, Any]) -> str:
        event_id = str(event.get("audit_id") or new_id("audit"))
        self.store.put("audit_events", event_id, {"audit_id": event_id, **dict(event)})
        return event_id

    def list(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("audit_events")
