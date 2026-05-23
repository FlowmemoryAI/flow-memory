"""Export chained audit events from a local SQLite store as deterministic JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import AuditStore, SQLiteStore, export_audit_event_log


def _ensure_sample_events(db: Path) -> None:
    audit = AuditStore(SQLiteStore(db))
    if audit.store.count("audit_events") == 0:
        audit.append_chained({"event": "public_alpha_event_log_started"})
        audit.append_chained({"event": "public_alpha_event_log_completed", "success": True})


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory audit event log JSONL")
    parser.add_argument("--db", type=Path, default=Path("release_evidence/event-log.sqlite3"), help="SQLite database path")
    parser.add_argument("--out", type=Path, default=Path("release_evidence/audit-events.jsonl"), help="Output JSONL path")
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    _ensure_sample_events(args.db)
    evidence = export_audit_event_log(SQLiteStore(args.db), args.out)
    payload = {"ok": evidence.replay_ok, "evidence": evidence.as_record(), "output": str(args.out)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if evidence.replay_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
