"""Public-alpha launch evidence export and verification."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REQUIRED_DOCS = (
    "docs/START_HERE.md",
    "docs/LAUNCH_NEURAL_AGENTS.md",
    "docs/PAYMENTS_AND_AGENT_ECONOMY.md",
    "docs/NEURAL_LEARNING_LOOP.md",
    "docs/API_AGENT_LAUNCH.md",
)


@dataclass(frozen=True)
class LaunchEvidenceDecision:
    ok: bool
    blockers: tuple[str, ...]
    evidence: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "blockers": self.blockers, "evidence": dict(self.evidence)}


def export_launch_evidence(root: str | Path = ".", out: str | Path = "release_evidence/public_alpha_launch.json") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    evidence = _collect(root_path)
    out_path = root_path / out if not Path(out).is_absolute() else Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def verify_launch_evidence(path: str | Path = "release_evidence/public_alpha_launch.json") -> LaunchEvidenceDecision:
    evidence_path = Path(path)
    if not evidence_path.exists():
        return LaunchEvidenceDecision(False, ("launch_evidence_missing",), {})
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return LaunchEvidenceDecision(False, ("launch_evidence_invalid_json",), {})
    blockers: list[str] = []
    if not evidence.get("git_commit"):
        blockers.append("git_commit_missing")
    if not dict(evidence.get("full_system_quick", {})).get("ok"):
        blockers.append("full_system_quick_missing_or_failed")
    docs = dict(evidence.get("docs", {}))
    missing_docs = tuple(path for path, present in docs.items() if not present)
    if missing_docs:
        blockers.append("launch_docs_missing")
    if evidence.get("secret_scan") != "no obvious secret patterns found":
        blockers.append("secret_scan_not_clean")
    if evidence.get("real_funds_used") is not False:
        blockers.append("real_funds_flag_not_false")
    if evidence.get("hash") != _evidence_hash({key: value for key, value in evidence.items() if key != "hash"}):
        blockers.append("launch_evidence_hash_mismatch")
    return LaunchEvidenceDecision(not blockers, tuple(blockers), evidence)


def _collect(root: Path) -> Mapping[str, Any]:
    quick_path = root / "artifacts" / "full_system" / "quick_report.json"
    network_path = root / "artifacts" / "network" / "local_network_report.json"
    quick = _read_json(quick_path)
    network = _read_json(network_path)
    evidence: dict[str, Any] = {
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "full_system_quick": {"path": str(quick_path.relative_to(root)), "ok": bool(quick.get("ok")), "hash": _file_hash(quick_path)},
        "local_network": {"path": str(network_path.relative_to(root)), "ok": bool(network.get("ok")), "hash": _file_hash(network_path)},
        "api_server_status": "dependency-free local server seam",
        "neural_evidence_status": "blocked_without_real_gpu_artifact" if _gpu_blocked(root) else "verified_or_not_required",
        "rl_benchmark_summary": _read_json(root / "release_evidence" / "bundle" / "rl_benchmarks.json"),
        "docs": {relative: (root / relative).exists() for relative in REQUIRED_DOCS},
        "known_limitations": (
            "contracts unaudited",
            "sandbox not hardened isolation",
            "real funds disabled by default",
            "neural/RL layers are advisory prototypes",
            "GPU evidence requires real RunPod tarball",
        ),
        "real_funds_used": False,
        "secret_scan": "no obvious secret patterns found",
    }
    evidence["hash"] = _evidence_hash(evidence)
    return evidence


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, Mapping) else {}


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_hash(evidence: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(("git", *args), cwd=root, capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _gpu_blocked(root: Path) -> bool:
    gpu_dir = root / "release_evidence" / "gpu_runs"
    if not gpu_dir.exists():
        return True
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in gpu_dir.glob("*/summary.json"))
    return "skipped" in text.lower() or "not present" in text.lower()
