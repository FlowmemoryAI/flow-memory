"""Provenance hash chains."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.crypto.hashes import content_hash


@dataclass(frozen=True)
class ProvenanceEntry:
    index: int
    payload: Mapping[str, Any]
    previous_hash: str
    entry_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {"index": self.index, "payload": dict(self.payload), "previous_hash": self.previous_hash, "entry_hash": self.entry_hash}


@dataclass
class ProvenanceChain:
    entries: list[ProvenanceEntry] = field(default_factory=list)

    def append(self, payload: Mapping[str, Any]) -> ProvenanceEntry:
        previous = self.entries[-1].entry_hash if self.entries else "genesis"
        entry_hash = content_hash({"index": len(self.entries), "payload": payload, "previous_hash": previous})
        entry = ProvenanceEntry(len(self.entries), dict(payload), previous, entry_hash)
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        previous = "genesis"
        for index, entry in enumerate(self.entries):
            if entry.index != index or entry.previous_hash != previous:
                return False
            expected = content_hash({"index": entry.index, "payload": entry.payload, "previous_hash": entry.previous_hash})
            if entry.entry_hash != expected:
                return False
            previous = entry.entry_hash
        return True
