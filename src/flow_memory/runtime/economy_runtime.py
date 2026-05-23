"""Economy runtime manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class EconomyRuntimeManager(BaseRuntimeManager):
    """Tracks local economy settlement health."""

    name: str = "economy"
    settlements: int = 0
    disputes: int = 0
    slashes: int = 0

    def record_settlement(self) -> None:
        self.settlements += 1

    def record_dispute(self) -> None:
        self.disputes += 1

    def record_slash(self) -> None:
        self.slashes += 1

    def summary(self) -> Mapping[str, object]:
        return {"settlements": self.settlements, "disputes": self.disputes, "slashes": self.slashes}
