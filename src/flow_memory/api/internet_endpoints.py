"""Local API handlers for Agent Internet."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_internet import (
    erc8004_export,
    get_agent_identity,
    get_collaboration,
    get_workspace,
    list_agent_identities,
    list_collaborations,
    list_mcp_manifests,
    match_skills,
    propose_collaboration,
    publish_skill_manifest,
    register_agent_identity,
    reputation_summary,
    simulate_payment_intent,
)

ROOT = Path(__file__).resolve().parents[3]


def internet_agents(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_agent_identities(root=root)
    return {"ok": True, "agents": records, "count": len(records)}


def internet_agent(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "agent": get_agent_identity(agent_id, root=root)}


def internet_agents_register(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", payload.get("local_agent_id", ""))))
    if not agent_id:
        raise ValueError("agent_id is required")
    return register_agent_identity(
        agent_id,
        display_name=str(payload.get("display_name", payload.get("name", agent_id))),
        description=str(payload.get("description", "Policy-gated Flow Memory agent node.")),
        genome_id=str(payload.get("genome_id", "")),
        root=root,
    )


def internet_skills_publish(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", "")))
    if not agent_id:
        raise ValueError("agent_id is required")
    skills = payload.get("skills", payload.get("skill", ()))
    if isinstance(skills, str):
        skills = (skills,)
    return publish_skill_manifest(agent_id, skills, domains=payload.get("domains", ()), root=root)


def internet_skills_match(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", payload.get("requester_agent_id", ""))))
    if not agent_id:
        raise ValueError("agent_id is required")
    return match_skills(
        agent_id,
        str(payload.get("task", payload.get("task_description", ""))),
        required_skills=payload.get("required_skills", ()),
        optional_skills=payload.get("optional_skills", ()),
        missing_skills=payload.get("missing_skills", ()),
        domain=str(payload.get("domain", "")),
        collaboration_style=str(payload.get("collaboration_style", "approval_required")),
        policy_constraints=payload.get("policy_constraints", ("approval_required", "no_raw_private_memory")),
        budget_policy=str(payload.get("budget_policy", "dry_run_only")),
        trust_minimum=float(payload.get("trust_minimum", 0.0) or 0.0),
        max_candidates=int(payload.get("max_candidates", 5) or 5),
        root=root,
    )


def internet_collaborations_propose(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return propose_collaboration(
        str(payload.get("from_agent_id", payload.get("from", ""))),
        str(payload.get("to_agent_id", payload.get("to", ""))),
        str(payload.get("task", payload.get("task_description", ""))),
        required_skills=payload.get("required_skills", ()),
        root=root,
    )


def internet_collaborations(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_collaborations(root=root)
    return {"ok": True, "collaborations": records, "count": len(records)}


def internet_collaboration(session_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "collaboration": get_collaboration(session_id, root=root)}


def internet_workspace(workspace_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "workspace": get_workspace(workspace_id, root=root)}


def internet_reputation(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "reputation": reputation_summary(agent_id, root=root)}


def internet_payment_intent_simulate(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return simulate_payment_intent(
        str(payload.get("from_agent_id", payload.get("from", ""))),
        str(payload.get("to_agent_id", payload.get("to", ""))),
        str(payload.get("resource", "collaboration")),
        float(payload.get("amount", 0.0) or 0.0),
        currency=str(payload.get("currency", "LOCAL")),
        root=root,
    )


def internet_erc8004(agent_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return erc8004_export(agent_id, root=root)


def internet_mcp_manifests(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_mcp_manifests(root=root)
    return {"ok": True, "manifests": records, "count": len(records)}
