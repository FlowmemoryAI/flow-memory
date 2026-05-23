"""Agent memory binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class AgentMemoryBinding:
    records: list[Mapping[str, Any]] = field(default_factory=list)

    def load_context(self, query: str) -> tuple[Mapping[str, Any], ...]:
        lowered = query.lower()
        matches = [record for record in self.records if lowered in str(record).lower()]
        return tuple(matches[-5:] if matches else self.records[-5:])

    def write(self, kind: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        record = {"kind": kind, "payload": dict(payload)}
        self.records.append(record)
        return record
