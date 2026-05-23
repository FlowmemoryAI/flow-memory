"""Base Sepolia artifact verification helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.crypto.hashes import content_hash
from flow_memory.web3.deployment_plan import CONTRACTS

REQUIRED_ARTIFACTS = (
    "deployment-plan.json",
    "dry-run-transactions.json",
    "contract-registry.json",
    "constructor-args.json",
    "dependency-graph.json",
    "risk-notes.md",
    "verification-checklist.md",
)


@dataclass(frozen=True)
class BaseArtifactValidation:
    ok: bool
    missing: tuple[str, ...]
    errors: tuple[str, ...]
    artifact_hashes: Mapping[str, str]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "missing": self.missing,
            "errors": self.errors,
            "artifact_hashes": dict(self.artifact_hashes),
        }


def validate_base_sepolia_artifacts(directory: str | Path) -> BaseArtifactValidation:
    base = Path(directory)
    missing = tuple(name for name in REQUIRED_ARTIFACTS if not (base / name).exists())
    errors: list[str] = []
    hashes: dict[str, str] = {}
    if missing:
        return BaseArtifactValidation(False, missing, ("missing required artifacts",), hashes)

    for name in REQUIRED_ARTIFACTS:
        path = base / name
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            hashes[name] = content_hash(payload)
        else:
            hashes[name] = content_hash(path.read_text(encoding="utf-8"))

    plan = json.loads((base / "deployment-plan.json").read_text(encoding="utf-8"))
    if plan.get("chain_id") != 84532:
        errors.append("deployment plan must target Base Sepolia chain id 84532")
    if plan.get("requires_private_key") is not False or plan.get("mode") != "dry-run":
        errors.append("deployment plan must be dry-run and require no private key")
    contract_names = tuple(item.get("name") for item in plan.get("contracts", ()))
    if contract_names != CONTRACTS:
        errors.append("deployment contract order does not match required contract list")

    transactions = json.loads((base / "dry-run-transactions.json").read_text(encoding="utf-8"))
    tx_names = tuple(item.get("contract") for item in transactions.get("transactions", ()))
    if tx_names != CONTRACTS:
        errors.append("dry-run transactions do not match deployment order")
    if any(item.get("dry_run") is not True for item in transactions.get("transactions", ())) :
        errors.append("all transaction payloads must be dry-run")

    registry = json.loads((base / "contract-registry.json").read_text(encoding="utf-8"))
    registry_names = tuple(registry.get("addresses", {}).keys())
    if tuple(sorted(registry_names)) != tuple(sorted(CONTRACTS)):
        errors.append("contract registry must include every required contract")

    return BaseArtifactValidation(not errors, (), tuple(errors), hashes)
