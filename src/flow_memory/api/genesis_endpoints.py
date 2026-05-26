"""Local API handlers for Agent Genesis."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_genesis import (
    birth_agent,
    create_teaching_event,
    export_contribution_bundle,
    get_genome,
    get_mirror,
    get_passport,
    list_archetypes,
    list_boundaries,
    list_contributions,
    list_instincts,
    write_teaching_event,
)

ROOT = Path(__file__).resolve().parents[3]


def genesis_archetypes(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_archetypes()
    return {"ok": True, "archetypes": records, "count": len(records)}


def genesis_instincts(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_instincts()
    return {"ok": True, "instincts": records, "count": len(records)}


def genesis_boundaries(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_boundaries()
    return {"ok": True, "boundaries": records, "count": len(records)}


def genesis_birth(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return birth_agent(payload, root=root)


def genesis_passport(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "passport": get_passport(agent_id, root=root)}


def genesis_genome(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "genome": get_genome(agent_id, root=root)}


def genesis_mirror(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "mirror": get_mirror(agent_id, root=root)}


def genesis_teaching(agent_id: str, payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    event = create_teaching_event(
        user_id=str(payload.get("user_id", payload.get("user", "local-user"))),
        agent_id=agent_id,
        correction_type=str(payload.get("correction_type", payload.get("type", "correction"))),
        content=str(payload.get("content", "")),
        lesson=str(payload.get("lesson", "Remember the user correction before repeating this action.")),
        applies_to_tags=tuple(str(item) for item in payload.get("applies_to_tags", payload.get("tags", ())) if str(item).strip()),
        contribution_allowed=bool(payload.get("contribution_allowed", False)),
    )
    return write_teaching_event(event, root=root)


def genesis_contributions(agent_id: str = "", root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_contributions(agent_id, root=root)
    return {"ok": True, "contributions": records, "count": len(records)}


def genesis_contributions_export(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", "")))
    out = str(payload.get("out", f"artifacts/genesis/contributions/{agent_id or 'all'}.json"))
    return export_contribution_bundle(agent_id, out, root=root)
