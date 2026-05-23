"""Replay and optionally restore a local audit event JSONL log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, event_log_evidence, read_jsonl_events, verify_chained_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay Flow Memory audit event log JSONL")
    parser.add_argument("--log", type=Path, default=Path("release_evidence/audit-events.jsonl"), help="Input JSONL event log")
    parser.add_argument("--restore-db", type=Path, default=Path("release_evidence/event-log-replay.sqlite3"), help="Optional empty/local SQLite database path to receive audit_events")
    parser.add_argument("--overwrite", action="store_true", default=True, help="Allow replacing audit event rows while restoring")
    args = parser.parse_args()

    events = read_jsonl_events(args.log)
    replay = verify_chained_events(events)
    restored = 0
    if replay.ok and args.restore_db is not None:
        store = SQLiteStore(args.restore_db)
        if not args.overwrite and store.list("audit_events"):
            raise ValueError("target audit_events table is not empty")
        for event in events:
            store.put("audit_events", str(event.get("audit_id") or event.get("event_id")), event)
            restored += 1

    evidence = event_log_evidence(events)
    payload = {
        "ok": replay.ok,
        "latest_hash": replay.latest_hash,
        "errors": replay.errors,
        "event_count": len(replay.records),
        "restored": restored,
        "evidence": evidence.as_record(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if replay.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
