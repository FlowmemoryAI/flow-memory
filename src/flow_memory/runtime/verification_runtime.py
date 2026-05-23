"""Verification runtime manager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class VerificationRuntimeManager(BaseRuntimeManager):
    """Tracks verifier decisions for local agent economy tasks."""

    name: str = "verification"
    accepted: int = 0
    rejected: int = 0

    def record_result(self, accepted: bool) -> None:
        if accepted:
            self.accepted += 1
        else:
            self.rejected += 1

    def summary(self) -> Mapping[str, object]:
        return {"accepted": self.accepted, "rejected": self.rejected}
