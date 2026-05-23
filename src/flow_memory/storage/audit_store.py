"""Audit event store."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.core.types import new_id
from flow_memory.storage.sqlite_store import SQLiteStore
from flow_memory.storage.replay import GENESIS_HASH, ReplayResult, chained_payload, verify_chained_events


class AuditStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def append(self, event: Mapping[str, Any]) -> str:
        event_id = str(event.get("audit_id") or new_id("audit"))
        self.store.put("audit_events", event_id, {"audit_id": event_id, **dict(event)})
        return event_id

    def append_chained(self, event: Mapping[str, Any]) -> str:
        event_id = str(event.get("audit_id") or new_id("audit"))
        chained_events = self.list_chained()
        previous_hash = str(chained_events[-1]["chain_hash"]) if chained_events else GENESIS_HASH
        payload = chained_payload({"audit_id": event_id, **dict(event)}, index=len(chained_events), previous_hash=previous_hash)
        self.store.put("audit_events", event_id, payload)
        return event_id

    def list_chained(self) -> tuple[Mapping[str, Any], ...]:
        chained_events = tuple(event for event in self.store.list("audit_events") if "chain_hash" in event)
        return tuple(sorted(chained_events, key=lambda event: int(event["chain_index"])))

    def verify_chained(self) -> ReplayResult:
        return verify_chained_events(self.list_chained())

    def list(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("audit_events")
