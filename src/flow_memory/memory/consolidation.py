"""Local memory consolidation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass
class MemoryConsolidator:
    max_items: int = 20

    def consolidate(self, records: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
        selected = tuple(records[: self.max_items])
        domains = tuple(sorted({str(record.get("domain", "unknown")) for record in selected}))
        return {"count": len(selected), "domains": domains, "summary": f"Consolidated {len(selected)} record(s) across {len(domains)} domain(s)."}
