"""Policy runtime manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class PolicyRuntimeManager(BaseRuntimeManager):
    """Tracks policy decisions and approval pressure."""

    name: str = "policy"
    approvals: int = 0
    denials: int = 0
    deferred: int = 0

    def record_decision(self, approved: bool, deferred: bool = False) -> None:
        if deferred:
            self.deferred += 1
        elif approved:
            self.approvals += 1
        else:
            self.denials += 1

    def summary(self) -> Mapping[str, object]:
        return {"approvals": self.approvals, "denials": self.denials, "deferred": self.deferred}
