"""Verify Flow Memory utility smoke evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def verify_utility_evidence(path: str | Path = "release_evidence/utility_evidence.json") -> dict[str, object]:
    evidence_path = Path(path)
    if not evidence_path.exists():
        return {"ok": False, "blockers": ("utility_evidence_missing",), "path": str(evidence_path)}
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "blockers": ("utility_evidence_invalid_json",), "path": str(evidence_path)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "blockers": ("utility_evidence_not_object",), "path": str(evidence_path)}
    blockers: list[str] = []
    expected_hash = hashlib.sha256(json.dumps({k: v for k, v in payload.items() if k != "hash"}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    if payload.get("hash") != expected_hash:
        blockers.append("utility_evidence_hash_mismatch")
    if payload.get("ok") is not True:
        blockers.append("utility_evidence_not_ok")
    for key in ("dashboard_api", "release_api", "rl_env_manifest", "payment_ledger_demo"):
        if dict(payload.get(key, {})).get("ok") is not True:
            blockers.append(f"{key}_not_ok")
    if payload.get("real_funds_used") is not False:
        blockers.append("real_funds_flag_not_false")
    if payload.get("raw_artifacts_exposed") is not False:
        blockers.append("raw_artifacts_exposed")
    return {"ok": not blockers, "blockers": tuple(dict.fromkeys(blockers)), "path": str(evidence_path), "evidence": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Flow Memory utility evidence")
    parser.add_argument("path", nargs="?", default="release_evidence/utility_evidence.json")
    args = parser.parse_args()
    result = verify_utility_evidence(args.path)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
