"""Create a portable Flow Memory storage backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, write_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Flow Memory SQLiteStore backup")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path")
    parser.add_argument("--out", type=Path, required=True, help="Backup JSON output path")
    args = parser.parse_args()

    output = write_backup(SQLiteStore(args.db), args.out)
    print(json.dumps({"ok": True, "backup": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
