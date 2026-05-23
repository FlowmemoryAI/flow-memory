"""JSONL export helpers."""

from __future__ import annotations

import json
from pathlib import Path

from flow_memory.storage.sqlite_store import SQLiteStore


def export_jsonl(store: SQLiteStore, table: str, path: str | Path) -> Path:
    output = Path(path)
    rows = store.list(table)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return output
