"""Squire control-plane API endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.squire import build_squire_goal_plan, inspect_squire_environment
from flow_memory.squire.docs_sync import docs_sync_plan
from flow_memory.squire.memory import economic_memory_schema
from flow_memory.squire.models import SquireRoutingPolicy
from flow_memory.squire.routing import default_route_candidates, choose_route

ROOT = Path(__file__).resolve().parents[3]


def squire_status() -> Mapping[str, Any]:
    env = inspect_squire_environment()
    return {
        "ok": True,
        "ecosystem": "squire",
        "posture": "live-first adapter seam",
        "environment": env.as_record(),
        "live_components": ("Level5 treasury/proxy", "UsePod register/fund/proxy", "agent-wallet HTTP 402 / MPP", "usepod-agent provider runtime"),
        "roadmap_not_claimed_live": ("TEE attestation", "on-chain slashing", "compute futures", "native SQUIRE redemption API"),
        "no_real_funds_by_default": True,
    }


def squire_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    goal = str(payload.get("goal", "Use Squire ecosystem routing for budgeted agentic inference"))
    return {"ok": True, "plan": build_squire_goal_plan(goal).as_record()}


def squire_routes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = SquireRoutingPolicy(
        marketplace_only=bool(payload.get("marketplace_only", False)),
        quality_sensitive=bool(payload.get("quality_sensitive", False)),
        max_input_price_per_million=float(payload.get("max_input_price_per_million", 0.0)),
        max_output_price_per_million=float(payload.get("max_output_price_per_million", 0.0)),
    )
    candidates = default_route_candidates()
    selected = choose_route(policy, candidates)
    return {"ok": True, "policy": policy.as_record(), "selected": selected.as_record(), "candidates": tuple(candidate.as_record() for candidate in candidates)}


def squire_memory_schema() -> Mapping[str, Any]:
    return {"ok": True, "schema_fields": economic_memory_schema(), "live_or_roadmap_required": True}


def squire_docs_sources() -> Mapping[str, Any]:
    return {"ok": True, "docs_sync": docs_sync_plan(enabled=False)}


def squire_skill_manifest() -> Mapping[str, Any]:
    path = ROOT / "skills" / "squire-goal" / "SKILL.md"
    return {
        "ok": path.exists(),
        "path": str(path.relative_to(ROOT)) if path.exists() else "skills/squire-goal/SKILL.md",
        "description_contains": ("SQUIRE", "Level5", "UsePod", "Solana", "budget", "routing", "402", "MPP", "provider", "marketplace"),
    }
