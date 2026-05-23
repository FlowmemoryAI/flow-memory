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

CONSTRUCTOR_ARGS: Mapping[str, tuple[object, ...]] = {
    "AgentRegistry": (),
    "TaskMarketplace": (),
    "TaskEscrow": (),
    "Reputation": ("dry_run_authority",),
    "AttestationRegistry": (),
    "DelegationRegistry": (),
    "DisputeResolver": ("dry_run_resolver",),
    "SlashingRegistry": ("dry_run_authority",),
    "CapabilityRegistry": (),
    "AgentTreasury": ("dry_run_controller",),
}

DEPENDENCIES: Mapping[str, tuple[str, ...]] = {
    "TaskMarketplace": ("AgentRegistry",),
    "TaskEscrow": ("TaskMarketplace",),
    "Reputation": ("AgentRegistry",),
    "AttestationRegistry": ("AgentRegistry",),
    "DelegationRegistry": ("AgentRegistry",),
    "DisputeResolver": ("TaskMarketplace",),
    "SlashingRegistry": ("DisputeResolver", "Reputation"),
    "CapabilityRegistry": ("AgentRegistry",),
    "AgentTreasury": ("TaskEscrow",),
}


def deployment_order() -> tuple[str, ...]:
    return CONTRACTS


def dependency_graph() -> Mapping[str, tuple[str, ...]]:
    return {name: tuple(DEPENDENCIES.get(name, ())) for name in CONTRACTS}


def constructor_args() -> Mapping[str, tuple[object, ...]]:
    return {name: tuple(CONSTRUCTOR_ARGS.get(name, ())) for name in CONTRACTS}


def expected_address_placeholders() -> Mapping[str, str]:
    return {name: "0x0000000000000000000000000000000000000000" for name in CONTRACTS}


def generate_deployment_plan(chain: str = "base-sepolia") -> Mapping[str, object]:
    return {
        "chain": chain,
        "chain_id": 84532 if chain == "base-sepolia" else 0,
        "mode": "dry-run",
        "requires_private_key": False,
        "deployment_order": deployment_order(),
        "dependency_graph": dependency_graph(),
        "constructor_args": constructor_args(),
        "expected_addresses": expected_address_placeholders(),
        "contracts": tuple(
            {
                "name": name,
                "action": "deploy",
                "constructor_args": tuple(CONSTRUCTOR_ARGS.get(name, ())),
                "depends_on": tuple(DEPENDENCIES.get(name, ())),
                "expected_address": "0x0000000000000000000000000000000000000000",
            }
            for name in CONTRACTS
        ),
        "safety": {
            "real_deployment_default": False,
            "private_key_required": False,
            "rpc_required": False,
            "funds_required": False,
        },
    }
