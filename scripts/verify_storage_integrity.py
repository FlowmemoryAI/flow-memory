"""Verify local storage integrity evidence without network dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, compare_store_to_backup_file, event_log_evidence, read_jsonl_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Flow Memory local storage integrity evidence")
    parser.add_argument("--db", type=Path, default=Path("release_evidence/event-log.sqlite3"), help="SQLite database path")
    parser.add_argument("--backup", type=Path, help="Optional deterministic backup JSON to compare")
    parser.add_argument("--event-log", type=Path, default=Path("release_evidence/audit-events.jsonl"), help="Optional audit event JSONL to replay")
    args = parser.parse_args()

    store = SQLiteStore(args.db)
    payload: dict[str, object] = {"ok": True, "scope": "local-prototype", "db": str(args.db)}
    if args.backup is not None:
        backup_report = compare_store_to_backup_file(store, args.backup)
        payload["backup"] = backup_report.as_record()
        payload["ok"] = bool(payload["ok"]) and backup_report.ok
    if args.event_log is not None:
        event_report = event_log_evidence(read_jsonl_events(args.event_log))
        payload["event_log"] = event_report.as_record()
        payload["ok"] = bool(payload["ok"]) and event_report.replay_ok

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if bool(payload["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
