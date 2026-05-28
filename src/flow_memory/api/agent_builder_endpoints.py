"""Local API handlers for Flow Memory Agent Builder."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_builder import birth_agent_from_builder, create_agent_builder_assembly_plan, agent_builder_defaults, simulate_agent_builder_upgrades

ROOT = Path(__file__).resolve().parents[3]


def agent_builder_defaults_endpoint(root: str | Path = ROOT) -> Mapping[str, Any]:
    return agent_builder_defaults()


def agent_builder_assembly_plan(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return create_agent_builder_assembly_plan(payload, root=root)


def agent_builder_birth(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return birth_agent_from_builder(payload, root=root)


def agent_builder_simulate_upgrades(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", ""))).strip()
    if not agent_id:
        raise ValueError("agent_id is required")
    return simulate_agent_builder_upgrades(
        agent_id,
        byok=bool(payload.get("byok", payload.get("byok_upgrade_requested", False))),
        wallet=bool(payload.get("wallet", payload.get("wallet_upgrade_requested", False))),
        onchain_dry_run=bool(payload.get("onchain_dry_run", payload.get("onchain_dry_run_requested", False))),
        x402=bool(payload.get("x402", payload.get("x402_dry_run_requested", False))),
        root=root,
    )
