"""Base Sepolia deployment plan generation."""

from __future__ import annotations

from typing import Mapping

CONTRACTS = (
    "AgentRegistry",
    "TaskMarketplace",
    "TaskEscrow",
    "Reputation",
    "AttestationRegistry",
    "DelegationRegistry",
    "DisputeResolver",
    "SlashingRegistry",
    "CapabilityRegistry",
    "AgentTreasury",
)


def generate_deployment_plan(chain: str = "base-sepolia") -> Mapping[str, object]:
    return {"chain": chain, "mode": "dry-run", "requires_private_key": False, "contracts": tuple({"name": name, "action": "deploy"} for name in CONTRACTS)}
