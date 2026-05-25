"""Public-alpha launch finalizer.

The finalizer is intentionally evidence-only: it does not start agents, contact
providers, run browsers, move funds, or rewrite launch artifacts. It composes the
already-generated local evidence into the final public-alpha operator handoff.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.release.launch_evidence import verify_launch_evidence
from flow_memory.release.live_3d_evidence import mission_control_live_3d_evidence
from flow_memory.release.neural_embodiment_evidence import neural_embodiment_evidence
from flow_memory.release.readiness import decide_release_readiness


PUBLIC_ALPHA_LAUNCH_FINALIZER_VERSION = "flow-memory-public-alpha-launch-finalizer-v1"
FINALIZER_DEFAULT_PATH = "release_evidence/public_alpha_launch_finalizer.json"
DEMO_BUNDLE_PATH = "artifacts/launch/bundles/public-alpha-local-demo.json"
FINALIZER_COMMANDS: tuple[Mapping[str, str], ...] = (
    {"label": "Run public-alpha launch test", "command": "python scripts/test_public_alpha_launch.py"},
    {"label": "Export launch evidence", "command": "python scripts/export_public_alpha_launch_evidence.py"},
    {"label": "Verify launch evidence", "command": "python scripts/verify_public_alpha_launch_evidence.py"},
    {"label": "Export release evidence bundle", "command": "python scripts/export_release_evidence.py --out release_evidence/bundle"},
    {"label": "Refresh Live 3D embodiment fixture", "command": "python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json"},
    {"label": "Finalize public alpha", "command": "python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json"},
    {"label": "Check GPU-backed public-alpha launch decision", "command": "python scripts/release_decision.py --target public-alpha-launch"},
    {"label": "Run Mission Control dashboard checks", "command": "cd dashboard && npm test && npm run build"},
)


@dataclass(frozen=True)
class PublicAlphaLaunchFinalizerDecision:
    ok: bool
    blockers: tuple[str, ...]
    finalizer: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "blockers": self.blockers, "finalizer": dict(self.finalizer)}


def finalize_public_alpha_launch(
    root: str | Path = ".",
    out: str | Path = FINALIZER_DEFAULT_PATH,
) -> Mapping[str, Any]:
    """Write and return the final public-alpha launch handoff record."""

    root_path = Path(root).resolve()
    launch_evidence_path = root_path / "release_evidence" / "public_alpha_launch.json"
    launch_evidence = verify_launch_evidence(launch_evidence_path).as_record()
    local_launch = decide_release_readiness(root_path, target="public-alpha-local-launch").as_record()
    gpu_launch = decide_release_readiness(root_path, target="public-alpha-launch").as_record()
    live_3d = mission_control_live_3d_evidence(root_path)
    embodiment = neural_embodiment_evidence(root_path)
    demo_bundle = _demo_bundle_status(root_path)
    tracked_backup_paths = _tracked_ctmp_backup_paths(root_path)
    blockers = _blockers(
        launch_evidence=launch_evidence,
        local_launch=local_launch,
        gpu_launch=gpu_launch,
        live_3d=live_3d,
        embodiment=embodiment,
        demo_bundle=demo_bundle,
        tracked_backup_paths=tracked_backup_paths,
    )
    record_without_hash: dict[str, Any] = {
        "ok": not blockers,
        "schema_version": PUBLIC_ALPHA_LAUNCH_FINALIZER_VERSION,
        "project": "Flow Memory",
        "release_target": "public-alpha-launch",
        "operator_handoff": "Mission Control Live 3D Mode + Public Alpha Launch Finalizer",
        "git": _git_status(root_path),
        "release_decisions": {
            "public-alpha-local-launch": local_launch,
            "public-alpha-launch": gpu_launch,
        },
        "launch_evidence": {
            "path": _rel(root_path, launch_evidence_path),
            "ok": launch_evidence.get("ok") is True,
            "blockers": tuple(launch_evidence.get("blockers", ())),
        },
        "mission_control_live_3d": _live_3d_summary(live_3d),
        "neural_embodiment": _embodiment_summary(embodiment),
        "public_alpha_demo_bundle": demo_bundle,
        "commands": FINALIZER_COMMANDS,
        "invariants": {
            "local_only": True,
            "read_only_operator_handoff": True,
            "neural_advisory_only": True,
            "policy_engine_and_approval_gate_authoritative": True,
            "no_external_model_calls": True,
            "no_live_provider_calls": True,
            "no_private_keys": True,
            "no_funds_moved": True,
            "no_broadcast": True,
            "no_live_settlement": True,
            "ctmp_backup_not_tracked": not tracked_backup_paths,
        },
        "ctmp_backup_tracked_paths": tracked_backup_paths,
        "blockers": blockers,
    }
    record = {**record_without_hash, "hash": _record_hash(record_without_hash)}
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = root_path / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return {**record, "finalizer_path": _rel(root_path, out_path)}


def verify_public_alpha_launch_finalizer(path: str | Path = FINALIZER_DEFAULT_PATH) -> PublicAlphaLaunchFinalizerDecision:
    """Verify a previously exported public-alpha launch finalizer record."""

    finalizer_path = Path(path)
    if not finalizer_path.exists():
        return PublicAlphaLaunchFinalizerDecision(False, ("public_alpha_launch_finalizer_missing",), {})
    try:
        record = json.loads(finalizer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return PublicAlphaLaunchFinalizerDecision(False, ("public_alpha_launch_finalizer_invalid_json",), {})
    if not isinstance(record, Mapping):
        return PublicAlphaLaunchFinalizerDecision(False, ("public_alpha_launch_finalizer_not_object",), {})
    blockers: list[str] = []
    if record.get("schema_version") != PUBLIC_ALPHA_LAUNCH_FINALIZER_VERSION:
        blockers.append("public_alpha_launch_finalizer_schema_mismatch")
    expected_hash = _record_hash({key: value for key, value in record.items() if key != "hash"})
    if record.get("hash") != expected_hash:
        blockers.append("public_alpha_launch_finalizer_hash_mismatch")
    if record.get("ok") is not True:
        blockers.extend(str(item) for item in record.get("blockers", ()))
        if not record.get("blockers"):
            blockers.append("public_alpha_launch_finalizer_not_ok")
    invariants = dict(record.get("invariants", {})) if isinstance(record.get("invariants", {}), Mapping) else {}
    required_invariants = (
        "local_only",
        "read_only_operator_handoff",
        "neural_advisory_only",
        "policy_engine_and_approval_gate_authoritative",
        "no_external_model_calls",
        "no_live_provider_calls",
        "no_private_keys",
        "no_funds_moved",
        "no_broadcast",
        "no_live_settlement",
        "ctmp_backup_not_tracked",
    )
    for invariant in required_invariants:
        if invariants.get(invariant) is not True:
            blockers.append(f"invariant_failed_{invariant}")
    decisions = dict(record.get("release_decisions", {})) if isinstance(record.get("release_decisions", {}), Mapping) else {}
    for target in ("public-alpha-local-launch", "public-alpha-launch"):
        decision = dict(decisions.get(target, {})) if isinstance(decisions.get(target, {}), Mapping) else {}
        if decision.get("ok") is not True:
            blockers.append(f"release_decision_not_ok_{target}")
    if dict(record.get("launch_evidence", {})).get("ok") is not True:
        blockers.append("launch_evidence_not_ok")
    if dict(record.get("mission_control_live_3d", {})).get("ok") is not True:
        blockers.append("mission_control_live_3d_not_ok")
    if dict(record.get("neural_embodiment", {})).get("ok") is not True:
        blockers.append("neural_embodiment_not_ok")
    if dict(record.get("public_alpha_demo_bundle", {})).get("ok") is not True:
        blockers.append("public_alpha_demo_bundle_not_ok")
    return PublicAlphaLaunchFinalizerDecision(not blockers, tuple(dict.fromkeys(blockers)), record)


def _blockers(
    *,
    launch_evidence: Mapping[str, Any],
    local_launch: Mapping[str, Any],
    gpu_launch: Mapping[str, Any],
    live_3d: Mapping[str, Any],
    embodiment: Mapping[str, Any],
    demo_bundle: Mapping[str, Any],
    tracked_backup_paths: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if launch_evidence.get("ok") is not True:
        blockers.append("public_alpha_launch_evidence_not_ok")
        blockers.extend(f"launch_evidence_{item}" for item in launch_evidence.get("blockers", ()))
    if local_launch.get("ok") is not True:
        blockers.append("public_alpha_local_launch_decision_not_ok")
        blockers.extend(f"local_launch_{item}" for item in local_launch.get("blockers", ()))
    if gpu_launch.get("ok") is not True:
        blockers.append("public_alpha_launch_decision_not_ok")
        blockers.extend(f"gpu_launch_{item}" for item in gpu_launch.get("blockers", ()))
    if live_3d.get("ok") is not True:
        blockers.append("mission_control_live_3d_not_ready")
    if embodiment.get("ok") is not True:
        blockers.append("neural_embodiment_not_ready")
    if demo_bundle.get("ok") is not True:
        blockers.append("public_alpha_demo_bundle_not_ready")
    if tracked_backup_paths:
        blockers.append("ctmp_backup_tracked")
    return tuple(dict.fromkeys(blockers))


def _live_3d_summary(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    sample = dict(evidence.get("sample", {})) if isinstance(evidence.get("sample", {}), Mapping) else {}
    return {
        "ok": evidence.get("ok") is True,
        "component_available": evidence.get("mission_control_live_3d_mode_available") is True,
        "data_ready": evidence.get("mission_control_live_3d_data_ready") is True,
        "docs_ready": evidence.get("mission_control_live_3d_docs_ready") is True,
        "no_overclaim": evidence.get("mission_control_live_3d_no_overclaim_invariant") is True,
        "component": evidence.get("component", ""),
        "fixture_path": evidence.get("fixture_path", ""),
        "sample": sample,
    }


def _embodiment_summary(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    sample = dict(evidence.get("sample", {})) if isinstance(evidence.get("sample", {}), Mapping) else {}
    return {
        "ok": evidence.get("ok") is True,
        "dashboard_available": evidence.get("neural_embodiment_dashboard_available") is True,
        "fixture_available": evidence.get("neural_embodiment_replay_fixture_available") is True,
        "gpu_status_visible": evidence.get("neural_embodiment_gpu_status_visible") is True,
        "policy_gate_visible": evidence.get("neural_embodiment_policy_gate_visible") is True,
        "memory_activation_visible": evidence.get("neural_embodiment_memory_activation_visible") is True,
        "learning_tick_visible": evidence.get("neural_embodiment_learning_tick_visible") is True,
        "no_overclaim": evidence.get("neural_embodiment_no_overclaim_invariant") is True,
        "sample": sample,
    }


def _demo_bundle_status(root: Path) -> Mapping[str, Any]:
    path = root / DEMO_BUNDLE_PATH
    payload = _read_json(path)
    invariants = dict(payload.get("invariants", {})) if isinstance(payload.get("invariants", {}), Mapping) else {}
    required = (
        "local_only",
        "neural_advisory_only",
        "policy_gated",
        "approval_gate_authoritative",
        "no_external_model_calls",
        "no_live_provider_calls",
        "no_private_keys",
        "no_funds_moved",
        "no_broadcast",
        "no_live_settlement",
    )
    missing = tuple(name for name in required if invariants.get(name) is not True)
    return {
        "ok": path.exists() and payload.get("ok") is True and not missing,
        "path": _rel(root, path),
        "bundle_hash": str(payload.get("bundle_hash", "")),
        "gpu_evidence_status": str(payload.get("gpu_evidence_status", "")),
        "missing_invariants": missing,
        "fixture_count": len(payload.get("mission_control_fixtures", ())) if isinstance(payload.get("mission_control_fixtures", ()), (list, tuple)) else 0,
    }


def _git_status(root: Path) -> Mapping[str, Any]:
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "tracked_ctmp_backup_paths": _tracked_ctmp_backup_paths(root),
    }


def _tracked_ctmp_backup_paths(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(("git", "ls-files"), cwd=root, capture_output=True, text=True)
    if completed.returncode != 0:
        return ()
    paths = []
    for relative in completed.stdout.splitlines():
        normalized = relative.replace("\\", "/").lower()
        if "ctmp-backup" in normalized or normalized.startswith("c:/tmp") or normalized.startswith("c/tmp"):
            paths.append(relative)
    return tuple(sorted(paths))


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(("git", *args), cwd=root, capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _record_hash(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
