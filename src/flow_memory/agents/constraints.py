"""Agent constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Constraint:
    rule: str
    severity: str = "must"

    def conflicts_with(self, text: str) -> bool:
        return self.rule.lower().startswith("do not") and self.rule[6:].strip().lower() in text.lower()

    def as_record(self) -> Mapping[str, str]:
        return {"rule": self.rule, "severity": self.severity}
