"""Evaluation history for Flow Memory learning reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class EvaluationHistory:
    records: list[Mapping[str, Any]] = field(default_factory=list)

    def add(self, record: Mapping[str, Any]) -> None:
        self.records.append(dict(record))

    def success_rate(self) -> float:
        if not self.records:
            return 0.0
        successes = sum(1 for record in self.records if bool(record.get("success", False)))
        return successes / len(self.records)

    def as_record(self) -> Mapping[str, Any]:
        return {"count": len(self.records), "success_rate": self.success_rate(), "records": tuple(dict(record) for record in self.records)}
