"""Restore a portable Flow Memory storage backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, restore_backup_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a Flow Memory SQLiteStore backup")
    parser.add_argument("--backup", type=Path, required=True, help="Backup JSON path")
    parser.add_argument("--db", type=Path, required=True, help="Target SQLite database path")
    parser.add_argument("--overwrite", action="store_true", help="Allow writing into a non-empty target store")
    args = parser.parse_args()

    manifest = restore_backup_file(args.backup, SQLiteStore(args.db), overwrite=args.overwrite)
    print(json.dumps({"ok": True, "manifest": manifest.as_record(), "database": str(args.db)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
