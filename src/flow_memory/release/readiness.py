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
LOCAL_PUBLIC_ALPHA_EVIDENCE = PUBLIC_ALPHA_EVIDENCE + (
    "full_system_quick",
    "launch_scripts",
    "local_network_visual_replay",
    "mission_control_docs",
    "compute_market",
    "neural_live_agents",
    "predictive_cognitive_core",
    "predictive_learning_benchmark",
    "agent_genesis_network_learning",
    "experience_graph_proof_of_learning",
    "live_agent_launchpad",
    "live_agent_operations",
    "live_agent_supervisor",
    "mission_control_run_console",
    "neural_embodiment",
)
PUBLIC_ALPHA_LOCAL_LAUNCH_EVIDENCE = LOCAL_PUBLIC_ALPHA_EVIDENCE + (
    "public_alpha_launch_test",
    "public_alpha_launch_evidence",
    "api_server_help",
    "payment_docs",
    "no_secret_scan_hits",
)
PUBLIC_ALPHA_LAUNCH_FINALIZER_EVIDENCE = tuple(dict.fromkeys(PUBLIC_ALPHA_LOCAL_LAUNCH_EVIDENCE + (
    "public_alpha_launch_test",
    "public_alpha_launch_evidence",
    "mission_control_live_3d",
    "public_alpha_launch_finalizer",
)))
AGENT_GENESIS_EVIDENCE = tuple(dict.fromkeys(LOCAL_PUBLIC_ALPHA_EVIDENCE + ("agent_genesis_network_learning",)))
PROOF_OF_LEARNING_EVIDENCE = tuple(dict.fromkeys(LOCAL_PUBLIC_ALPHA_EVIDENCE + ("experience_graph_proof_of_learning",)))


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
    elif target == "public-alpha-launch":
        blockers = _public_alpha_launch_blockers(root_path, gates.ok)
        classification = "public_alpha_launch_candidate" if not blockers else "blocked_public_alpha_launch"
        evidence = PUBLIC_ALPHA_NEURAL_EVIDENCE + ("full_system_quick", "launch_docs", "payment_docs", "learning_docs")
    elif target == "local-public-alpha":
        blockers = _local_public_alpha_blockers(root_path, gates.ok)
        classification = "local_public_alpha_candidate" if not blockers else "blocked_local_public_alpha"
        evidence = LOCAL_PUBLIC_ALPHA_EVIDENCE
    elif target == "public-alpha-local-launch":
        blockers = _public_alpha_local_launch_blockers(root_path, gates.ok)
        classification = "public_alpha_local_launch_candidate" if not blockers else "blocked_public_alpha_local_launch"
        evidence = PUBLIC_ALPHA_LOCAL_LAUNCH_EVIDENCE
    elif target == "public-alpha-launch-finalizer":
        blockers = _public_alpha_launch_finalizer_blockers(root_path, gates.ok)
        classification = "public_alpha_launch_finalizer_candidate" if not blockers else "blocked_public_alpha_launch_finalizer"
        evidence = PUBLIC_ALPHA_LAUNCH_FINALIZER_EVIDENCE
    elif target == "public-alpha-cognition":
        blockers = _public_alpha_cognition_blockers(root_path, gates.ok)
        classification = "public_alpha_cognition_candidate" if not blockers else "blocked_public_alpha_cognition"
        evidence = LOCAL_PUBLIC_ALPHA_EVIDENCE
    elif target == "public-alpha-genesis":
        blockers = _public_alpha_genesis_blockers(root_path, gates.ok)
        classification = "public_alpha_genesis_candidate" if not blockers else "blocked_public_alpha_genesis"
        evidence = AGENT_GENESIS_EVIDENCE
    elif target == "public-alpha-proof-of-learning":
        blockers = _public_alpha_proof_of_learning_blockers(root_path, gates.ok)
        classification = "public_alpha_proof_of_learning_candidate" if not blockers else "blocked_public_alpha_proof_of_learning"
        evidence = PROOF_OF_LEARNING_EVIDENCE
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

def _public_alpha_launch_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_public_alpha_neural_blockers(root, gate_ok))
    full_system = root / "artifacts" / "full_system" / "quick_report.json"
    if not full_system.exists():
        blockers.append("full_system_quick_missing")
    else:
        try:
            if json.loads(full_system.read_text(encoding="utf-8")).get("ok") is not True:
                blockers.append("full_system_quick_failed")
        except json.JSONDecodeError:
            blockers.append("full_system_quick_invalid")
    required_docs = (
        "docs/START_HERE.md",
        "docs/LAUNCH_NEURAL_AGENTS.md",
        "docs/PAYMENTS_AND_AGENT_ECONOMY.md",
        "docs/NEURAL_LEARNING_LOOP.md",
    )
    for relative in required_docs:
        if not (root / relative).exists():
            blockers.append(f"missing_{relative.replace('/', '_')}")
    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8").lower() if readme.exists() else ""
    if "public alpha" not in readme_text and "public-alpha" not in readme_text:
        blockers.append("readme_public_alpha_warning_missing")
    if "not audited" not in readme_text and "audited contracts" not in readme_text:
        blockers.append("readme_audit_warning_missing")
    if "mainnet" not in readme_text:
        blockers.append("readme_mainnet_warning_missing")
    return tuple(dict.fromkeys(blockers))


def _local_public_alpha_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_public_alpha_blockers(root, gate_ok))
    quick = root / "artifacts" / "full_system" / "quick_report.json"
    if not quick.exists():
        blockers.append("full_system_quick_missing")
    else:
        try:
            if json.loads(quick.read_text(encoding="utf-8")).get("ok") is not True:
                blockers.append("full_system_quick_failed")
        except json.JSONDecodeError:
            blockers.append("full_system_quick_invalid")
    for relative in (
        "scripts/launch_local_agent.py",
        "scripts/launch_flowlang_agent.py",
        "scripts/launch_neural_agent.py",
        "scripts/launch_local_agent_network.py",
        "scripts/run_local_network.py",
        "scripts/export_visual_replay.py",
    ):
        if not (root / relative).exists():
            blockers.append(f"missing_{relative.replace('/', '_')}")
    replay = root / "dashboard" / "src" / "mock-data" / "local-network-replay.json"
    if not replay.exists():
        blockers.append("visual_replay_missing")
    else:
        try:
            payload = json.loads(replay.read_text(encoding="utf-8"))
            state = dict(payload.get("state", {}))
            if payload.get("ok") is not True or not state.get("agents") or not state.get("tasks"):
                blockers.append("visual_replay_invalid")
        except json.JSONDecodeError:
            blockers.append("visual_replay_invalid")
    required_docs = (
        "docs/START_HERE.md",
        "docs/LAUNCH_NEURAL_AGENTS.md",
        "docs/PAYMENTS_AND_AGENT_ECONOMY.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
    )
    for relative in required_docs:
        if not (root / relative).exists():
            blockers.append(f"missing_{relative.replace('/', '_')}")
    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8").lower() if readme.exists() else ""
    if "public alpha" not in readme_text and "public-alpha" not in readme_text:
        blockers.append("readme_public_alpha_warning_missing")
    if "not audited" not in readme_text:
        blockers.append("readme_audit_warning_missing")
    if "not mainnet" not in readme_text and "mainnet-ready" not in readme_text:
        blockers.append("readme_mainnet_warning_missing")
    try:
        from flow_memory.release.compute_evidence import compute_market_evidence

        if not compute_market_evidence(root).get("ok"):
            blockers.append("compute_market_evidence_missing_or_invalid")
    except Exception:
        blockers.append("compute_market_evidence_missing_or_invalid")
    try:
        from flow_memory.release.neural_live_evidence import neural_live_evidence

        if not neural_live_evidence(root).get("ok"):
            blockers.append("neural_live_evidence_missing_or_invalid")
    except Exception:
        blockers.append("neural_live_evidence_missing_or_invalid")
    try:
        from flow_memory.release.predictive_cognitive_evidence import predictive_cognitive_core_evidence

        if not predictive_cognitive_core_evidence(root).get("ok"):
            blockers.append("predictive_cognitive_core_evidence_missing_or_invalid")
    except Exception:
        blockers.append("predictive_cognitive_core_evidence_missing_or_invalid")
    try:
        from flow_memory.release.predictive_learning_evidence import predictive_learning_benchmark_evidence

        if not predictive_learning_benchmark_evidence(root).get("ok"):
            blockers.append("predictive_learning_benchmark_evidence_missing_or_invalid")
    except Exception:
        blockers.append("predictive_learning_benchmark_evidence_missing_or_invalid")
    try:
        from flow_memory.release.agent_genesis_evidence import agent_genesis_network_learning_evidence

        if not agent_genesis_network_learning_evidence(root).get("ok"):
            blockers.append("agent_genesis_network_learning_evidence_missing_or_invalid")
    except Exception:
        blockers.append("agent_genesis_network_learning_evidence_missing_or_invalid")
    try:
        from flow_memory.release.proof_of_learning_evidence import experience_graph_proof_of_learning_evidence

        if not experience_graph_proof_of_learning_evidence(root).get("ok"):
            blockers.append("experience_graph_proof_of_learning_evidence_missing_or_invalid")
    except Exception:
        blockers.append("experience_graph_proof_of_learning_evidence_missing_or_invalid")
    try:
        from flow_memory.release.launchpad_evidence import live_agent_launchpad_evidence

        if not live_agent_launchpad_evidence(root).get("ok"):
            blockers.append("live_agent_launchpad_evidence_missing_or_invalid")
    except Exception:
        blockers.append("live_agent_launchpad_evidence_missing_or_invalid")
    try:
        from flow_memory.release.launch_operations_evidence import live_agent_operations_evidence

        if not live_agent_operations_evidence(root).get("ok"):
            blockers.append("live_agent_operations_evidence_missing_or_invalid")
    except Exception:
        blockers.append("live_agent_operations_evidence_missing_or_invalid")
    try:
        from flow_memory.release.launch_supervisor_evidence import live_agent_supervisor_evidence

        if not live_agent_supervisor_evidence(root).get("ok"):
            blockers.append("live_agent_supervisor_evidence_missing_or_invalid")
    except Exception:
        blockers.append("live_agent_supervisor_evidence_missing_or_invalid")
    try:
        from flow_memory.release.run_console_evidence import mission_control_run_console_evidence

        if not mission_control_run_console_evidence(root).get("ok"):
            blockers.append("mission_control_run_console_evidence_missing_or_invalid")
    except Exception:
        blockers.append("mission_control_run_console_evidence_missing_or_invalid")
    try:
        from flow_memory.release.neural_embodiment_evidence import neural_embodiment_evidence

        if not neural_embodiment_evidence(root).get("ok"):
            blockers.append("neural_embodiment_evidence_missing_or_invalid")
    except Exception:
        blockers.append("neural_embodiment_evidence_missing_or_invalid")
    return tuple(dict.fromkeys(blockers))

def _public_alpha_local_launch_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_local_public_alpha_blockers(root, gate_ok))
    launch_report = root / "artifacts" / "public_alpha_launch" / "launch_report.json"
    if not launch_report.exists():
        blockers.append("public_alpha_launch_test_missing")
    else:
        try:
            report = json.loads(launch_report.read_text(encoding="utf-8"))
            if report.get("ok") is not True:
                blockers.append("public_alpha_launch_test_failed")
            checks = dict(report.get("checks", {}))
            required_checks = (
                "cli",
                "flowlang",
                "neural",
                "local_network",
                "visual_replay",
                "api_help",
                "release_local_public_alpha",
            )
            for check_name in required_checks:
                if not dict(checks.get(check_name, {})).get("ok"):
                    blockers.append(f"public_alpha_launch_check_failed_{check_name}")
        except json.JSONDecodeError:
            blockers.append("public_alpha_launch_test_invalid")
    evidence_path = root / "release_evidence" / "public_alpha_launch.json"
    if not evidence_path.exists():
        blockers.append("public_alpha_launch_evidence_missing")
    else:
        try:
            from flow_memory.release.launch_evidence import verify_launch_evidence

            decision = verify_launch_evidence(evidence_path)
            if not decision.ok:
                blockers.extend(f"public_alpha_launch_evidence_{blocker}" for blocker in decision.blockers)
        except Exception:
            blockers.append("public_alpha_launch_evidence_invalid")
    return tuple(dict.fromkeys(blockers))

def _public_alpha_cognition_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_local_public_alpha_blockers(root, gate_ok))
    try:
        from flow_memory.release.predictive_learning_evidence import predictive_learning_benchmark_evidence, verify_predictive_learning_benchmark_evidence

        decision = verify_predictive_learning_benchmark_evidence(predictive_learning_benchmark_evidence(root))
        if not decision.get("ok"):
            blockers.extend(f"predictive_learning_{blocker}" for blocker in decision.get("blockers", ()))
    except Exception:
        blockers.append("predictive_learning_benchmark_evidence_missing_or_invalid")
    return tuple(dict.fromkeys(blockers))
def _public_alpha_genesis_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_local_public_alpha_blockers(root, gate_ok))
    try:
        from flow_memory.release.agent_genesis_evidence import (
            agent_genesis_network_learning_evidence,
            verify_agent_genesis_network_learning_evidence,
        )

        decision = verify_agent_genesis_network_learning_evidence(agent_genesis_network_learning_evidence(root))
        if not decision.get("ok"):
            blockers.extend(f"agent_genesis_{blocker}" for blocker in decision.get("blockers", ()))
    except Exception:
        blockers.append("agent_genesis_network_learning_evidence_missing_or_invalid")
    return tuple(dict.fromkeys(blockers))

def _public_alpha_proof_of_learning_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_local_public_alpha_blockers(root, gate_ok))
    try:
        from flow_memory.release.proof_of_learning_evidence import (
            experience_graph_proof_of_learning_evidence,
            verify_experience_graph_proof_of_learning_evidence,
        )

        decision = verify_experience_graph_proof_of_learning_evidence(experience_graph_proof_of_learning_evidence(root))
        if not decision.get("ok"):
            blockers.extend(f"proof_of_learning_{blocker}" for blocker in decision.get("blockers", ()))
    except Exception:
        blockers.append("experience_graph_proof_of_learning_evidence_missing_or_invalid")
    return tuple(dict.fromkeys(blockers))

def _public_alpha_launch_finalizer_blockers(root: Path, gate_ok: bool) -> tuple[str, ...]:
    blockers = list(_public_alpha_local_launch_blockers(root, gate_ok))
    blockers.extend(_public_alpha_launch_blockers(root, gate_ok))
    try:
        from flow_memory.release.live_3d_evidence import mission_control_live_3d_evidence

        if not mission_control_live_3d_evidence(root).get("ok"):
            blockers.append("mission_control_live_3d_evidence_missing_or_invalid")
    except Exception:
        blockers.append("mission_control_live_3d_evidence_missing_or_invalid")
    finalizer_path = root / "release_evidence" / "public_alpha_launch_finalizer.json"
    if not finalizer_path.exists():
        blockers.append("public_alpha_launch_finalizer_missing")
    else:
        try:
            from flow_memory.release.launch_finalizer import verify_public_alpha_launch_finalizer

            decision = verify_public_alpha_launch_finalizer(finalizer_path)
            if not decision.ok:
                blockers.extend(f"public_alpha_launch_finalizer_{blocker}" for blocker in decision.blockers)
        except Exception:
            blockers.append("public_alpha_launch_finalizer_invalid")
    return tuple(dict.fromkeys(blockers))


def _gpu_report(path: Path) -> Mapping[str, Any]:
    try:
        from flow_memory.neural.gpu_evidence import verify_gpu_run

        return dict(verify_gpu_run(path))
    except Exception:
        return {"ok": False, "runs": ()}
