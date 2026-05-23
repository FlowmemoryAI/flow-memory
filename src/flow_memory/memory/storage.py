"""Local memory persistence helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from flow_memory.core.types import MemoryRecord


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return repr(value)


@dataclass
class JsonlMemoryStore:
    """Append-only JSONL store for episodic records."""

    path: Path

    def append(self, record: MemoryRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True, default=_json_default) + "\n")

    def read_all(self) -> tuple[Mapping[str, Any], ...]:
        if not self.path.exists():
            return ()
        rows: list[Mapping[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return tuple(rows)

    def extend(self, records: Iterable[MemoryRecord]) -> None:
        for record in records:
            self.append(record)
