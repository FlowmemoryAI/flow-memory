"""Marketplace runtime manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class MarketplaceRuntimeManager(BaseRuntimeManager):
    """Tracks local marketplace task flow."""

    name: str = "marketplace"
    open_tasks: int = 0
    assigned_tasks: int = 0
    settled_tasks: int = 0

    def record_task(self, status: str) -> None:
        if status == "open":
            self.open_tasks += 1
        elif status == "assigned":
            self.assigned_tasks += 1
        elif status == "settled":
            self.settled_tasks += 1

    def summary(self) -> Mapping[str, object]:
        return {"open": self.open_tasks, "assigned": self.assigned_tasks, "settled": self.settled_tasks}
