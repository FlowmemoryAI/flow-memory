"""Regression-test plan records for self-improvement."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class RegressionTestPlan:
    target_id: str
    commands: Sequence[str]
    plan_id: str = field(default_factory=lambda: new_id("regression_plan"))

    def as_record(self) -> dict[str, object]:
        return {"plan_id": self.plan_id, "target_id": self.target_id, "commands": tuple(self.commands)}
