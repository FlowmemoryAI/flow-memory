"""Local release-readiness gates.

These gates intentionally avoid network calls, real keys, and external services.
They are meant to catch accidental API drift, broken audit replay, unsafe dry-run
configuration, and obvious checked-in secrets before a public release.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from flow_memory.api.snapshot import validate_api_snapshot
from flow_memory.crypto.keys import generate_local_keypair
from flow_memory.storage import AuditStore, SQLiteStore, create_audit_checkpoint, verify_audit_checkpoint, verify_schema
from flow_memory.web3.deployment_plan import generate_deployment_plan

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"BEGIN" r" PRIVATE KEY",
        r"PRIVATE_KEY\s*=",
        r"DEEPSEEK_API_KEY\s*=",
        r"MOONSHOT_API_KEY\s*=",
        r"OPENAI_API_KEY\s*=",
        r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-]+",
        r"cfat_[A-Za-z0-9]+",
        r"gho_[A-Za-z0-9]+",
        r"sk-proj-[A-Za-z0-9_\-]+",
        r"sk-live-[A-Za-z0-9_\-]+",
    )
)
_SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "target", "out", "cache", ".pytest_cache", "__pycache__"})
_SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".db", ".sqlite", ".sqlite3"})


@dataclass(frozen=True)
class ReleaseGateResult:
    name: str
    ok: bool
    details: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"name": self.name, "ok": self.ok, "details": dict(self.details)}


@dataclass(frozen=True)
class ReleaseGateReport:
    ok: bool
    results: tuple[ReleaseGateResult, ...]

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "results": tuple(result.as_record() for result in self.results)}


def run_release_gates(root: str | Path = ".") -> ReleaseGateReport:
    root_path = Path(root).resolve()
    results = (
        _api_snapshot_gate(root_path),
        _audit_replay_gate(),
        _base_dry_run_gate(),
        _storage_schema_gate(),
        _secret_scan_gate(root_path),
    )
    return ReleaseGateReport(ok=all(result.ok for result in results), results=results)


def _api_snapshot_gate(root: Path) -> ReleaseGateResult:
    snapshot_path = root / "docs" / "API_SNAPSHOT.json"
    if not snapshot_path.exists():
        return ReleaseGateResult("api_snapshot", False, {"error": "docs/API_SNAPSHOT.json missing"})
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validation = validate_api_snapshot(snapshot)
    return ReleaseGateResult("api_snapshot", validation.ok, {"errors": validation.errors})


def _audit_replay_gate() -> ReleaseGateResult:
    with tempfile.TemporaryDirectory() as tmp:
        audit = AuditStore(SQLiteStore(Path(tmp) / "audit.sqlite3"))
        audit.append_chained({"event": "release_gate_started"})
        audit.append_chained({"event": "release_gate_completed", "success": True})
        replay = audit.verify_chained()
        key = generate_local_keypair("release-gate-local-dev")
        checkpoint = create_audit_checkpoint(replay, key)
        checkpoint_ok = verify_audit_checkpoint(
            checkpoint,
            key,
            expected_latest_hash=replay.latest_hash,
            expected_event_count=len(replay.records),
        )
    return ReleaseGateResult(
        "audit_replay",
        replay.ok and checkpoint_ok,
        {"replay_ok": replay.ok, "checkpoint_ok": checkpoint_ok, "event_count": len(replay.records)},
    )


def _base_dry_run_gate() -> ReleaseGateResult:
    plan = generate_deployment_plan()
    ok = plan.get("mode") == "dry-run" and plan.get("requires_private_key") is False
    return ReleaseGateResult("base_dry_run", ok, {"mode": plan.get("mode"), "requires_private_key": plan.get("requires_private_key")})


def _storage_schema_gate() -> ReleaseGateResult:
    verification = verify_schema(SQLiteStore())
    return ReleaseGateResult(
        "storage_schema",
        verification.ok,
        {
            "observed_version": verification.observed_version,
            "expected_version": verification.expected_version,
            "missing_tables": verification.missing_tables,
            "schema_hash": verification.schema_hash,
        },
    )


def _secret_scan_gate(root: Path) -> ReleaseGateResult:
    matches = tuple(_secret_matches(root))
    return ReleaseGateResult("secret_scan", not matches, {"match_count": len(matches), "paths": matches[:20]})


def _secret_matches(root: Path) -> Iterable[str]:
    for path in root.rglob("*"):
        if not path.is_file() or _should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                yield str(path.relative_to(root))
                break


def _should_skip(path: Path) -> bool:
    if any(part in _SKIP_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return True
    try:
        return path.stat().st_size > 1_000_000
    except OSError:
        return True
