"""Verify Flow Memory SQLiteStore schema and migration metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, migration_plan, verify_schema


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Flow Memory SQLite storage schema")
    parser.add_argument("--db", type=Path, default=Path(":memory:"), help="SQLite database path; defaults to in-memory")
    args = parser.parse_args()

    store = SQLiteStore(":memory:" if str(args.db) == ":memory:" else args.db)
    verification = verify_schema(store)
    payload = {"ok": verification.ok, "schema": verification.as_record(), "migration_plan": migration_plan().as_record()}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if verification.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
