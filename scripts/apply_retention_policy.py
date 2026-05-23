"""Apply a local Flow Memory storage retention policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.storage import SQLiteStore, apply_retention_policy, policy_from_mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Flow Memory SQLiteStore retention policy")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path")
    parser.add_argument("--policy", type=Path, required=True, help="Retention policy JSON path")
    args = parser.parse_args()

    policy = policy_from_mapping(json.loads(args.policy.read_text(encoding="utf-8")))
    report = apply_retention_policy(SQLiteStore(args.db), policy)
    print(json.dumps(report.as_record(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
