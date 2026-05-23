"""Replay and optionally checkpoint a Flow Memory SQLite audit log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.crypto.keys import generate_local_keypair
from flow_memory.storage.audit_store import AuditStore
from flow_memory.storage.checkpoints import create_audit_checkpoint
from flow_memory.storage.sqlite_store import SQLiteStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay Flow Memory SQLite audit events")
    parser.add_argument("--db", type=Path, default=Path("flow-memory.sqlite3"), help="SQLite database path")
    parser.add_argument("--checkpoint", action="store_true", help="Emit an ephemeral local-dev signed checkpoint")
    parser.add_argument("--require-events", action="store_true", help="Fail if the audit log is empty")
    args = parser.parse_args()

    store = SQLiteStore(args.db)
    audit = AuditStore(store)
    result = audit.verify_chained()
    payload: dict[str, object] = dict(result.as_record())
    payload["database"] = str(args.db)
    if args.checkpoint:
        key = generate_local_keypair("audit-replay-local-dev")
        payload["checkpoint"] = create_audit_checkpoint(result, key).as_record()
        payload["checkpoint_key"] = key.as_public_record()
        payload["checkpoint_warning"] = "local development HMAC key is ephemeral; use production key custody before relying on checkpoints"

    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_events and not result.records:
        return 2
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
