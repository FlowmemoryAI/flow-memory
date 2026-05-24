"""Release readiness decisions for Flow Memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.release.gates import run_release_gates
from flow_memory.web3.verification import validate_base_sepolia_artifacts

PRODUCTION_BLOCKERS = (
    "contracts_unaudited",
    "sandbox_not_hardened",
    "production_key_custody_missing",
    "mainnet_deployment_disabled",
)

PUBLIC_ALPHA_EVIDENCE = (
    "release_gates",
    "api_snapshot",
    "storage_schema",
    "base_dry_run",
    "dependency_inventory",
    "dependency_policy",
    "clean_clone_validation",
    "base_sepolia_artifacts",
    "openapi_snapshot",
)
NEURAL_GPU_EVIDENCE = PUBLIC_ALPHA_EVIDENCE + ("gpu_evidence",)
PUBLIC_ALPHA_NEURAL_EVIDENCE = NEURAL_GPU_EVIDENCE + ("rl_benchmarks",)


@dataclass(frozen=True)
class ReleaseReadinessDecision:
    target: str
    ok: bool
    classification: str
    gate_ok: bool
    blockers: tuple[str, ...]
    required_evidence: tuple[str, ...]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "target": self.target,
            "ok": self.ok,
            "classification": self.classification,
            "gate_ok": self.gate_ok,
            "blockers": self.blockers,
            "required_evidence": self.required_evidence,
        }


def decide_release_readiness(root: str | Path = ".", *, target: str = "local") -> ReleaseReadinessDecision:
    """Return an explicit go/no-go decision for a release target."""

    root_path = Path(root).resolve()
    gates = run_release_gates(root_path)
    if target == "local":
        blockers: tuple[str, ...] = () if gates.ok else ("release_gates_failed",)
        classification = "local_release_candidate" if gates.ok else "blocked_local_release"
        evidence = ("release_gates", "api_snapshot", "storage_schema", "base_dry_run", "dependency_inventory")
    elif target == "public-alpha":
        blockers = _public_alpha_blockers(root_path, gates.ok)
        classification = "public_alpha_preflight_candidate" if not blockers else "blocked_public_alpha_preflight"
        evidence = PUBLIC_ALPHA_EVIDENCE
    elif target in {"testnet", "testnet-dry-run"}:
        blockers = _public_alpha_blockers(root_path, gates.ok)
        if not blockers:
            blockers = ("testnet_manual_review_required",)
        classification = "testnet_dry_run_review_candidate" if gates.ok else "blocked_testnet_dry_run"
        evidence = PUBLIC_ALPHA_EVIDENCE + ("contract_registry", "dry_run_deployment_plan")
    elif target == "neural-gpu-smoke":
        blockers = _neural_gpu_blockers(root_path, gates.ok)
        classification = "neural_gpu_smoke_candidate" if not blockers else "neural_gpu_smoke_local_skip"
        evidence = NEURAL_GPU_EVIDENCE
    elif target == "public-alpha-neural":
        blockers = _public_alpha_neural_blockers(root_path, gates.ok)
        classification = "public_alpha_neural_candidate" if not blockers else "blocked_public_alpha_neural"
        evidence = PUBLIC_ALPHA_NEURAL_EVIDENCE
    elif target == "production":
        blockers = (("release_gates_failed",) if not gates.ok else ()) + PRODUCTION_BLOCKERS
        classification = "blocked_production_release"
        evidence = (
            "external_contract_audit",
            "hardened_sandbox_evidence",
            "production_key_custody_runbook",
            "mainnet_deployment_approval",
            "incident_response_runbook",
            "dependency_inventory",
        )
    else:
        raise ValueError(f"unknown release target: {target}")
    return ReleaseReadinessDecision(
        target=target,
        ok=gates.ok and not blockers,
        classification=classification,
        gate_ok=gates.ok,
        blockers=blockers,
        required_evidence=evidence,
    )


def _public_alpha_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers: list[str] = []
    if not gate_ok:
        blockers.append("release_gates_failed")
    clean_clone = root / "release_evidence" / "clean_clone_validation.json"
    if not clean_clone.exists():
        blockers.append("clean_clone_validation_missing")
    else:
        try:
            if json.loads(clean_clone.read_text(encoding="utf-8")).get("ok") is not True:
                blockers.append("clean_clone_validation_failed")
        except json.JSONDecodeError:
            blockers.append("clean_clone_validation_invalid")
    base_artifacts = validate_base_sepolia_artifacts(root / "deployments" / "base-sepolia")
    if not base_artifacts.ok:
        blockers.append("base_sepolia_artifacts_invalid")
    if not (root / "docs" / "openapi" / "flow-memory.openapi.json").exists():
        blockers.append("openapi_snapshot_missing")
    return tuple(blockers)


def _neural_gpu_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_public_alpha_blockers(root, gate_ok))
    evidence = root / "release_evidence" / "gpu_runs"
    if not evidence.exists():
        blockers.append("gpu_evidence_missing")
        return tuple(blockers)
    report = _gpu_report(evidence)
    runs = tuple(report.get("runs", ()))
    if not runs:
        blockers.append("gpu_evidence_missing")
        return tuple(blockers)
    if not report.get("ok"):
        blockers.append("gpu_evidence_invalid")
    verified = any(
        bool(record.get("ok"))
        and not bool(dict(record.get("summary", {})).get("skipped", False))
        for record in runs
    )
    if not verified:
        blockers.append("gpu_evidence_verified_run_missing")
    return tuple(blockers)

def _public_alpha_neural_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_neural_gpu_blockers(root, gate_ok))
    try:
        from flow_memory.release.rl_evidence import rl_benchmark_evidence, verify_rl_benchmark_evidence

        report = verify_rl_benchmark_evidence(rl_benchmark_evidence(root))
    except Exception:
        report = {"ok": False, "benchmark_count": 0}
    if not report.get("ok"):
        blockers.append("rl_benchmark_evidence_missing")
    return tuple(blockers)


def _gpu_report(path: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.neural.gpu_evidence import verify_gpu_run

        return dict(verify_gpu_run(path))
    except Exception:
        return {"ok": False, "runs": ()}
