"""Verify a live Flow Memory SQLiteStore against a deterministic backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, compare_store_to_backup_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify live Flow Memory storage against a backup JSON file")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path")
    parser.add_argument("--backup", type=Path, required=True, help="Backup JSON path")
    args = parser.parse_args()

    report = compare_store_to_backup_file(SQLiteStore(args.db), args.backup)
    print(json.dumps(report.as_record(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
