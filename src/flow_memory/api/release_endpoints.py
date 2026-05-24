"""Release evidence endpoint handlers for the local API router."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping



ROOT = Path(__file__).resolve().parents[3]
ALLOWED_TARGETS = {"local", "neural-gpu-smoke", "public-alpha-neural", "public-alpha-launch"}


def release_evidence_status(root: str | Path = ROOT) -> Mapping[str, Any]:
    root_path = Path(root)
    bundle_dir = root_path / "release_evidence" / "bundle"
    index_path = bundle_dir / "index.json"
    if not index_path.exists():
        return {"ok": False, "bundle_exists": False, "path": str(index_path.relative_to(root_path)), "raw_artifacts_exposed": False}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    files = tuple(index.get("files", ()))
    return {
        "ok": True,
        "bundle_exists": True,
        "path": str(index_path.relative_to(root_path)),
        "bundle_hash": index.get("bundle_hash", ""),
        "files": files,
        "file_count": len(files),
        "raw_artifacts_exposed": False,
    }


def release_decision_status(target: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    from flow_memory.release.readiness import decide_release_readiness
    normalized = target.strip()
    if normalized not in ALLOWED_TARGETS:
        raise ValueError(f"unsupported release decision target: {target}")
    decision = decide_release_readiness(root, target=normalized).as_record()
    return {"ok": bool(decision.get("ok")), "decision": decision, "target": normalized}
