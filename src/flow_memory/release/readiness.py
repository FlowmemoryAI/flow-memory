"""Release readiness decisions for Flow Memory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.release.gates import run_release_gates

PRODUCTION_BLOCKERS = (
    "contracts_unaudited",
    "sandbox_not_hardened",
    "production_key_custody_missing",
    "mainnet_deployment_disabled",
)


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
    """Return an explicit go/no-go decision for a release target.

    Targets:
    - ``local``: local development/demo release with no production claims.
    - ``testnet``: non-mainnet dry-run/testnet candidate; requires gates but still
      carries blockers for funds/security claims.
    - ``production``: intentionally fails until audited contracts, hardened sandbox,
      production key custody, and mainnet controls exist.
    """

    gates = run_release_gates(root)
    if target == "local":
        blockers: tuple[str, ...] = () if gates.ok else ("release_gates_failed",)
        classification = "local_release_candidate" if gates.ok else "blocked_local_release"
        evidence = ("release_gates", "api_snapshot", "storage_schema", "base_dry_run", "dependency_inventory")
    elif target == "testnet":
        blockers = ("testnet_manual_review_required",) if gates.ok else ("release_gates_failed", "testnet_manual_review_required")
        classification = "testnet_review_candidate" if gates.ok else "blocked_testnet_release"
        evidence = ("release_gates", "release_manifest", "contract_registry", "dry_run_deployment_plan", "dependency_inventory")
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
