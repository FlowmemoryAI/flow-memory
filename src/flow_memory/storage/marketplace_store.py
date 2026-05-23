"""Marketplace persistence."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.storage.sqlite_store import SQLiteStore


class MarketplaceStore:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_task(self, task_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("marketplace_tasks", task_id, payload)

    def load_task(self, task_id: str) -> Mapping[str, Any] | None:
        return self.store.get("marketplace_tasks", task_id)

    def save_bid(self, bid_id: str, payload: Mapping[str, Any]) -> None:
        self.store.put("bids", bid_id, payload)

    def list_tasks(self) -> tuple[Mapping[str, Any], ...]:
        return self.store.list("marketplace_tasks")
