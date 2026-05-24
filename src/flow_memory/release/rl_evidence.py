"""RL benchmark evidence collection for release bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def rl_benchmark_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    artifact_dir = root_path / "artifacts" / "rl"
    if not artifact_dir.exists():
        return {"ok": True, "skipped": True, "reason": "artifacts/rl directory absent", "benchmarks": ()}
    records = []
    for path in sorted(artifact_dir.glob("rl_*benchmark*.json")):
        records.append(_record(root_path, path))
    return {
        "ok": True,
        "skipped": not records,
        "reason": "no RL benchmark artifacts found" if not records else "",
        "benchmarks": tuple(records),
        "benchmark_count": len(records),
    }


def verify_rl_benchmark_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    records = tuple(evidence.get("benchmarks", ()))
    invalid = tuple(record for record in records if not record.get("sha256") or not record.get("name"))
    return {"ok": not invalid and bool(records), "benchmark_count": len(records), "invalid_count": len(invalid)}


def _record(root: Path, path: Path) -> Mapping[str, Any]:
    payload: Mapping[str, Any] = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            payload = loaded
    except json.JSONDecodeError:
        payload = {"ok": False, "error": "invalid JSON"}
    data = path.read_bytes()
    return {
        "name": path.stem,
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "ok": bool(payload.get("ok", False)),
        "summary": _summary(payload),
    }


def _summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    keys = ("env_id", "best_policy", "tabular_q_improved", "prototype_metric", "steps_per_second")
    return {key: payload[key] for key in keys if key in payload}
