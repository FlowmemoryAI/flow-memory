"""Public-alpha launch evidence export and verification."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REQUIRED_DOCS = (
    "docs/START_HERE.md",
    "docs/LAUNCH_NEURAL_AGENTS.md",
    "docs/LOCAL_NETWORK_QUICKSTART.md",
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/AGENT_ECONOMY_QUICKSTART.md",
    "docs/RL_ARENA_QUICKSTART.md",
    "docs/PAYMENTS_AND_AGENT_ECONOMY.md",
    "docs/PUBLIC_ALPHA_READINESS.md",
    "docs/FAQ.md",
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
    if not dict(evidence.get("public_alpha_launch_test", {})).get("ok"):
        blockers.append("public_alpha_launch_test_missing_or_failed")
    if not dict(evidence.get("local_network", {})).get("ok"):
        blockers.append("local_network_missing_or_failed")
    api_status = dict(evidence.get("api_server_status", {}))
    if api_status.get("ok") is not True:
        blockers.append("api_server_help_missing_or_failed")
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
    dashboard = dict(evidence.get("dashboard_mock_snapshot", {}))
    if dashboard.get("mock_data_only") is not True or dashboard.get("ok") is not True:
        blockers.append("dashboard_mock_snapshot_missing")
    if dict(evidence.get("live_agent_launchpad", {})).get("ok") is not True:
        blockers.append("live_agent_launchpad_missing_or_failed")
    if dict(evidence.get("live_agent_operations", {})).get("ok") is not True:
        blockers.append("live_agent_operations_missing_or_failed")
    if dict(evidence.get("live_agent_supervisor", {})).get("ok") is not True:
        blockers.append("live_agent_supervisor_missing_or_failed")
    if dict(evidence.get("mission_control_run_console", {})).get("ok") is not True:
        blockers.append("mission_control_run_console_missing_or_failed")
    if dict(evidence.get("public_alpha_demo_bundle", {})).get("ok") is not True:
        blockers.append("public_alpha_demo_bundle_missing_or_failed")
    if dict(evidence.get("mission_control_live_3d", {})).get("ok") is not True:
        blockers.append("mission_control_live_3d_missing_or_failed")
    return LaunchEvidenceDecision(not blockers, tuple(blockers), evidence)


def _collect(root: Path) -> Mapping[str, Any]:
    quick_path = root / "artifacts" / "full_system" / "quick_report.json"
    network_path = root / "artifacts" / "network" / "local_network_report.json"
    launch_report_path = root / "artifacts" / "public_alpha_launch" / "launch_report.json"
    quick = _read_json(quick_path)
    network = _read_json(network_path)
    launch_report = _read_json(launch_report_path)
    evidence: dict[str, Any] = {
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "full_system_quick": {"path": str(quick_path.relative_to(root)), "ok": bool(quick.get("ok")), "hash": _file_hash(quick_path)},
        "local_network": {"path": str(network_path.relative_to(root)), "ok": bool(network.get("ok")), "hash": _file_hash(network_path)},
        "public_alpha_launch_test": {"path": str(launch_report_path.relative_to(root)), "ok": bool(launch_report.get("ok")), "hash": _file_hash(launch_report_path)},
        "api_server_status": _api_server_help_status(root, launch_report),
        "neural_evidence_status": "blocked_without_real_gpu_artifact" if _gpu_blocked(root) else "verified_runpod_artifact",
        "rl_benchmark_summary": _read_json(root / "release_evidence" / "bundle" / "rl_benchmarks.json"),
        "live_agent_launchpad": _live_agent_launchpad_status(root),
        "live_agent_operations": _live_agent_operations_status(root),
        "live_agent_supervisor": _live_agent_supervisor_status(root),
        "mission_control_run_console": _mission_control_run_console_status(root),
        "public_alpha_demo_bundle": _public_alpha_demo_bundle_status(root),
        "mission_control_live_3d": _mission_control_live_3d_status(root),
        "docs": {relative: (root / relative).exists() for relative in REQUIRED_DOCS},
        "dashboard_mock_snapshot": _dashboard_mock_snapshot(root),
        "known_limitations": (
            "contracts unaudited",
            "sandbox not hardened isolation",
            "real funds disabled by default",
            "neural/RL layers are advisory prototypes",
            "GPU evidence is imported release evidence, not production ML certification",
        ),
        "real_funds_used": False,
        "secret_scan": _secret_scan_status(root),
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

def _api_server_help_status(root: Path, launch_report: Mapping[str, Any]) -> Mapping[str, Any]:
    checks = dict(launch_report.get("checks", {}))
    api_help = dict(checks.get("api_help", {}))
    script_present = (root / "scripts" / "run_local_api_server.py").exists()
    return {
        "ok": bool(api_help.get("ok")) if checks else script_present,
        "script_present": script_present,
        "source": "public_alpha_launch_test" if checks else "script_presence",
    }

def _live_agent_launchpad_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.release.launchpad_evidence import live_agent_launchpad_evidence

        evidence = live_agent_launchpad_evidence(root)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": bool(evidence.get("ok")),
        "cli": bool(evidence.get("launchpad_cli_available")),
        "api": bool(evidence.get("launchpad_api_available")),
        "templates": tuple(evidence.get("launch_templates_available", ())),
        "gpu_status_honest": bool(evidence.get("launch_gpu_status_honest")),
    }

def _live_agent_operations_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.release.launch_operations_evidence import live_agent_operations_evidence

        evidence = live_agent_operations_evidence(root)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": bool(evidence.get("ok")),
        "registry": bool(evidence.get("live_agent_operations_registry_available")),
        "cli": bool(evidence.get("live_agent_operations_cli_available")),
        "api": bool(evidence.get("live_agent_operations_api_available")),
        "replay": bool(evidence.get("live_agent_operations_replay_available")),
        "export": bool(evidence.get("live_agent_operations_export_available")),
        "gpu_status_honest": bool(evidence.get("live_agent_operations_gpu_status_honest")),
    }

def _live_agent_supervisor_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.release.launch_supervisor_evidence import live_agent_supervisor_evidence

        evidence = live_agent_supervisor_evidence(root)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": bool(evidence.get("ok")),
        "cli": bool(evidence.get("live_agent_supervisor_cli_available")),
        "api": bool(evidence.get("live_agent_supervisor_api_available")),
        "heartbeat": bool(evidence.get("live_agent_supervisor_heartbeat_validated")),
        "pause_resume": bool(evidence.get("live_agent_supervisor_pause_resume_validated")),
        "visual_replay": bool(dict(evidence.get("live_agent_supervisor_visual_replay_validated", {})).get("ok")),
        "gpu_status_honest": bool(evidence.get("live_agent_supervisor_gpu_status_honest")),
    }

def _mission_control_run_console_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.release.run_console_evidence import mission_control_run_console_evidence

        evidence = mission_control_run_console_evidence(root)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": bool(evidence.get("ok")),
        "selector": bool(evidence.get("mission_control_run_selector_available")),
        "status_card": bool(evidence.get("mission_control_run_status_card_available")),
        "fixtures": bool(evidence.get("mission_control_replay_fixture_selector_validated")),
        "dev_server": bool(evidence.get("mission_control_dev_server_renders_real_dashboard")),
    }

def _mission_control_live_3d_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.release.live_3d_evidence import mission_control_live_3d_evidence

        evidence = mission_control_live_3d_evidence(root)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": bool(evidence.get("ok")),
        "component": bool(evidence.get("mission_control_live_3d_mode_available")),
        "data_ready": bool(evidence.get("mission_control_live_3d_data_ready")),
        "docs_ready": bool(evidence.get("mission_control_live_3d_docs_ready")),
        "no_overclaim": bool(evidence.get("mission_control_live_3d_no_overclaim_invariant")),
    }


def _public_alpha_demo_bundle_status(root: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.visualization.run_console import build_public_alpha_demo_bundle

        out = root / "artifacts" / "launch" / "bundles" / "public-alpha-local-demo.json"
        bundle = build_public_alpha_demo_bundle(root, out)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    invariants = dict(bundle.get("invariants", {})) if isinstance(bundle.get("invariants", {}), Mapping) else {}
    return {
        "ok": bool(bundle.get("ok")) and invariants.get("no_external_model_calls") is True and invariants.get("no_funds_moved") is True,
        "path": bundle.get("bundle_path", ""),
        "gpu_status_honest": bundle.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"},
    }


def _secret_scan_status(root: Path) -> str:
    patterns = (
        re.compile(r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PRIVATE) KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"(?i)(seed phrase|mnemonic)\s*[:=]\s*[a-z]+(?:\s+[a-z]+){11,23}"),
    )
    completed = subprocess.run(("git", "ls-files"), cwd=root, capture_output=True, text=True)
    paths = completed.stdout.splitlines() if completed.returncode == 0 else []
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in patterns):
            return "possible secret patterns found"
    return "no obvious secret patterns found"


def _gpu_blocked(root: Path) -> bool:
    gpu_dir = root / "release_evidence" / "gpu_runs"
    if not gpu_dir.exists():
        return True
    summaries = []
    for path in gpu_dir.glob("*/summary.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            summaries.append(payload)
    return not any(summary.get("ok") is True and summary.get("skipped") is not True for summary in summaries)


def _dashboard_mock_snapshot(root: Path) -> Mapping[str, Any]:
    mock_dir = root / "dashboard" / "src" / "mock-data"
    expected = (
        "runtime.json",
        "neural-status.json",
        "rl-benchmarks.json",
        "agent-launch.json",
        "local-network.json",
        "payments.json",
    )
    missing = tuple(name for name in expected if not (mock_dir / name).exists())
    file_hashes = {
        name: _file_hash(mock_dir / name)
        for name in expected
        if (mock_dir / name).exists()
    }
    return {
        "ok": not missing,
        "mock_data_only": True,
        "missing": missing,
        "files": tuple(file_hashes),
        "file_hashes": file_hashes,
        "bundle_hash": hashlib.sha256(json.dumps(file_hashes, sort_keys=True).encode("utf-8")).hexdigest() if file_hashes else "",
    }
