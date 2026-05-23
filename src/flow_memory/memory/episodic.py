"""Episodic memory: append-only timeline plus vector retrieval."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from flow_memory.core.types import MemoryRecord

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def tokens(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    numerator = sum(a[token] * b[token] for token in a.keys() & b.keys())
    denom_a = math.sqrt(sum(value * value for value in a.values()))
    denom_b = math.sqrt(sum(value * value for value in b.values()))
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return numerator / (denom_a * denom_b)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return repr(value)


@dataclass
class EpisodicMemory:
    """Append-only timeline plus simple lexical vector retrieval."""

    path: Path | None = None
    _records: list[MemoryRecord] = field(default_factory=list, init=False, repr=False)
    _vectors: dict[str, Counter[str]] = field(default_factory=dict, init=False, repr=False)

    def append(self, record: MemoryRecord) -> MemoryRecord:
        self._records.append(record)
        self._vectors[record.record_id] = Counter(tokens(record.text))
        if self.path is not None:
            self._append_jsonl(self.path, record)
        return record

    def record(self, kind: str, text: str, payload: Mapping[str, Any] | None = None, importance: float = 0.5) -> MemoryRecord:
        return self.append(MemoryRecord(kind=kind, text=text, payload=payload or {}, importance=importance))

    def retrieve(self, query: str, limit: int = 5) -> tuple[MemoryRecord, ...]:
        query_vector = Counter(tokens(query))
        scored: list[tuple[float, MemoryRecord]] = []
        for record in self._records:
            lexical = cosine(query_vector, self._vectors.get(record.record_id, Counter()))
            score = lexical * 0.85 + record.importance * 0.15
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
        return tuple(record for _, record in scored[:limit])

    def timeline(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)

    def _append_jsonl(self, path: Path, record: MemoryRecord) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True, default=_json_default) + "\n")

    def save_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in self._records:
                handle.write(json.dumps(asdict(record), sort_keys=True, default=_json_default) + "\n")

    def load_jsonl(self, path: Path | None = None) -> int:
        source = path or self.path
        if source is None or not source.exists():
            return 0
        count = 0
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            created = data.get("created_at")
            if isinstance(created, str):
                data["created_at"] = datetime.fromisoformat(created)
            record = MemoryRecord(**data)
            self._records.append(record)
            self._vectors[record.record_id] = Counter(tokens(record.text))
            count += 1
        return count
