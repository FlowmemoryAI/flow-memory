"""Local in-memory adapter used by default."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class LocalMemoryAdapter:
    records: list[Mapping[str, object]] = field(default_factory=list)

    def write(self, record: Mapping[str, object]) -> Mapping[str, object]:
        stored = dict(record)
        self.records.append(stored)
        return stored

    def query(self, domain: str | None = None) -> tuple[Mapping[str, object], ...]:
        if domain is None:
            return tuple(dict(record) for record in self.records)
        return tuple(dict(record) for record in self.records if record.get("domain") == domain)
