"""Memory runtime manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class MemoryRuntimeManager(BaseRuntimeManager):
    """Tracks local memory maintenance activity."""

    name: str = "memory"
    consolidations: int = 0
    policy_denials: int = 0

    def record_consolidation(self) -> None:
        self.consolidations += 1

    def record_policy_denial(self) -> None:
        self.policy_denials += 1

    def summary(self) -> Mapping[str, object]:
        return {"consolidations": self.consolidations, "policy_denials": self.policy_denials}
