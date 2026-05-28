"""Local Agent Internet, skill matching, collaboration, and dry-run adapter models."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_ROOT = Path("artifacts/agent_internet")
DEFAULT_SKILL_CATEGORIES = (
    "research",
    "coding",
    "memory",
    "prediction",
    "planning",
    "verification",
    "market_analysis",
    "compute_routing",
    "visual_dashboard",
    "documentation",
    "teaching",
    "safety_review",
)


@dataclass(frozen=True)
class AgentNetworkIdentity:
    network_agent_id: str
    local_agent_id: str
    genome_id: str = ""
    display_name: str = ""
    description: str = ""
    owner_scope: str = "local"
    active: bool = True
    service_endpoints: tuple[str, ...] = ()
    mcp_endpoint_refs: tuple[str, ...] = ()
    skill_manifest_ref: str = ""
    reputation_ref: str = ""
    contribution_policy: Mapping[str, Any] = field(default_factory=lambda: {"mode": "private_only", "raw_private_memory_shared": False})
    privacy_policy: Mapping[str, Any] = field(default_factory=lambda: {"private_memory_excluded": True, "network_learning_opt_in": False})
    payment_capability: str = "none"
    capability_status: Mapping[str, Any] = field(default_factory=lambda: {"byok": "not_bound", "wallet": "not_bound", "onchain": "not_prepared", "emergency_stop": "clear"})
    byok_capability_status: str = "not_bound"
    wallet_binding_status: str = "not_bound"
    onchain_upgrade_status: str = "not_prepared"
    emergency_stop_status: str = "clear"
    trust_modes: tuple[str, ...] = ("local", "policy_only")
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "network_agent_id": self.network_agent_id,
            "local_agent_id": self.local_agent_id,
            "genome_id": self.genome_id,
            "display_name": self.display_name,
            "description": self.description,
            "owner_scope": self.owner_scope,
            "active": self.active,
            "service_endpoints": self.service_endpoints,
            "mcp_endpoint_refs": self.mcp_endpoint_refs,
            "skill_manifest_ref": self.skill_manifest_ref,
            "reputation_ref": self.reputation_ref,
            "contribution_policy": dict(self.contribution_policy),
            "privacy_policy": dict(self.privacy_policy),
            "payment_capability": self.payment_capability,
            "capability_status": dict(self.capability_status),
            "byok_capability_status": self.byok_capability_status,
            "wallet_binding_status": self.wallet_binding_status,
            "onchain_upgrade_status": self.onchain_upgrade_status,
            "emergency_stop_status": self.emergency_stop_status,
            "trust_modes": self.trust_modes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class AgentSkill:
    skill_id: str
    name: str
    description: str = ""
    category: str = "research"
    proficiency: float = 0.5
    confidence: float = 0.5
    evidence_refs: tuple[str, ...] = ()
    benchmark_refs: tuple[str, ...] = ()
    requires_approval: bool = True
    policy_tags: tuple[str, ...] = ("policy_gated",)
    cost_hint: str = "local"
    dry_run_supported: bool = True

    def as_record(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "proficiency": round(float(self.proficiency), 4),
            "confidence": round(float(self.confidence), 4),
            "evidence_refs": self.evidence_refs,
            "benchmark_refs": self.benchmark_refs,
            "requires_approval": self.requires_approval,
            "policy_tags": self.policy_tags,
            "cost_hint": self.cost_hint,
            "dry_run_supported": self.dry_run_supported,
        }


@dataclass(frozen=True)
class AgentSkillManifest:
    manifest_id: str
    agent_id: str
    skills: tuple[Mapping[str, Any], ...]
    tools: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    preferred_tasks: tuple[str, ...] = ()
    unavailable_tasks: tuple[str, ...] = ()
    collaboration_preferences: Mapping[str, Any] = field(default_factory=lambda: {"approval_required": True})
    input_formats: tuple[str, ...] = ("text", "json")
    output_formats: tuple[str, ...] = ("summary", "artifact", "json")
    mcp_tools: tuple[Mapping[str, Any], ...] = ()
    safety_constraints: tuple[str, ...] = ("approval_required", "no_raw_private_memory", "policy_gated")
    evidence_refs: tuple[str, ...] = ()
    project_history_refs: tuple[str, ...] = ()
    updated_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "agent_id": self.agent_id,
            "skills": tuple(dict(item) for item in self.skills),
            "tools": self.tools,
            "domains": self.domains,
            "preferred_tasks": self.preferred_tasks,
            "unavailable_tasks": self.unavailable_tasks,
            "collaboration_preferences": dict(self.collaboration_preferences),
            "input_formats": self.input_formats,
            "output_formats": self.output_formats,
            "mcp_tools": tuple(dict(item) for item in self.mcp_tools),
            "safety_constraints": self.safety_constraints,
            "evidence_refs": self.evidence_refs,
            "project_history_refs": self.project_history_refs,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class SkillMatchResult:
    match_id: str
    requester_agent_id: str
    task_description: str
    ranked_candidates: tuple[Mapping[str, Any], ...]
    score_breakdown: Mapping[str, Any]
    recommended_collaborator_ids: tuple[str, ...]
    rejected_candidates: tuple[Mapping[str, Any], ...]
    policy_warnings: tuple[str, ...]
    explanation: str
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "requester_agent_id": self.requester_agent_id,
            "task_description": self.task_description,
            "ranked_candidates": tuple(dict(item) for item in self.ranked_candidates),
            "score_breakdown": dict(self.score_breakdown),
            "recommended_collaborator_ids": self.recommended_collaborator_ids,
            "rejected_candidates": tuple(dict(item) for item in self.rejected_candidates),
            "policy_warnings": self.policy_warnings,
            "explanation": self.explanation,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CollaborationRequest:
    request_id: str
    requester_agent_id: str
    candidate_agent_id: str
    task_description: str
    required_skills: tuple[str, ...]
    proposed_role: str = "collaborator"
    shared_workspace_id: str = ""
    policy_requirements: tuple[str, ...] = ("approval_required", "no_raw_private_memory")
    payment_intent_ref: str = ""
    status: str = "proposed"
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requester_agent_id": self.requester_agent_id,
            "candidate_agent_id": self.candidate_agent_id,
            "task_description": self.task_description,
            "required_skills": self.required_skills,
            "proposed_role": self.proposed_role,
            "shared_workspace_id": self.shared_workspace_id,
            "policy_requirements": self.policy_requirements,
            "payment_intent_ref": self.payment_intent_ref,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CollaborationSession:
    session_id: str
    agent_ids: tuple[str, ...]
    roles: Mapping[str, str]
    shared_workspace_id: str
    task_id: str
    project_id: str
    policy_state: Mapping[str, Any]
    status: str = "accepted"
    messages_summary: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    experience_refs: tuple[str, ...] = ()
    reputation_events: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)
    completed_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_ids": self.agent_ids,
            "roles": dict(self.roles),
            "shared_workspace_id": self.shared_workspace_id,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "policy_state": dict(self.policy_state),
            "status": self.status,
            "messages_summary": self.messages_summary,
            "artifacts": self.artifacts,
            "experience_refs": self.experience_refs,
            "reputation_events": self.reputation_events,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class ProjectGraph:
    graph_id: str
    project_id: str
    nodes: tuple[Mapping[str, Any], ...]
    edges: tuple[Mapping[str, Any], ...]
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {"graph_id": self.graph_id, "project_id": self.project_id, "nodes": self.nodes, "edges": self.edges, "created_at": self.created_at}


@dataclass(frozen=True)
class SharedCognitiveWorkspace:
    workspace_id: str
    project_id: str
    participating_agent_ids: tuple[str, ...]
    task_context: str
    predictions: tuple[Mapping[str, Any], ...] = ()
    decisions: tuple[Mapping[str, Any], ...] = ()
    policy_checks: tuple[Mapping[str, Any], ...] = ()
    artifacts: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    resolved_questions: tuple[str, ...] = ()
    lessons: tuple[str, ...] = ()
    audit_events: tuple[Mapping[str, Any], ...] = ()
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "participating_agent_ids": self.participating_agent_ids,
            "task_context": self.task_context,
            "predictions": self.predictions,
            "decisions": self.decisions,
            "policy_checks": self.policy_checks,
            "artifacts": self.artifacts,
            "citations": self.citations,
            "open_questions": self.open_questions,
            "resolved_questions": self.resolved_questions,
            "lessons": self.lessons,
            "audit_events": self.audit_events,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class KnowledgeArtifact:
    artifact_id: str
    agent_id: str
    title: str
    summary: str
    citations: tuple[str, ...] = ()
    privacy_mode: str = "private_only"
    sanitized: bool = True
    raw_private_memory_excluded: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "summary": self.summary,
            "citations": self.citations,
            "privacy_mode": self.privacy_mode,
            "sanitized": self.sanitized,
            "raw_private_memory_excluded": self.raw_private_memory_excluded,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ReputationEvent:
    event_id: str
    agent_id: str
    event_type: str
    source_session_id: str
    score_delta: float
    reason: str
    evidence_refs: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "source_session_id": self.source_session_id,
            "score_delta": round(float(self.score_delta), 4),
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class PaymentIntent:
    intent_id: str
    requester_agent_id: str
    provider_agent_id: str
    resource: str
    amount: float
    currency: str = "LOCAL"
    rail: str = "dry_run_x402"
    http_status_simulation: str = "402_required"
    policy_state: Mapping[str, Any] = field(default_factory=lambda: {"allowed": True, "dry_run_only": True})
    settlement_state: str = "dry_run_only"
    no_private_key_required: bool = True
    no_broadcast: bool = True
    no_funds_moved: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "requester_agent_id": self.requester_agent_id,
            "provider_agent_id": self.provider_agent_id,
            "resource": self.resource,
            "amount": round(float(self.amount), 6),
            "currency": self.currency,
            "rail": self.rail,
            "http_status_simulation": self.http_status_simulation,
            "policy_state": dict(self.policy_state),
            "settlement_state": self.settlement_state,
            "no_private_key_required": self.no_private_key_required,
            "no_broadcast": self.no_broadcast,
            "no_funds_moved": self.no_funds_moved,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class MCPToolManifest:
    tool_id: str
    name: str
    description: str
    endpoint_ref: str
    transport: str = "local"
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    permissions: tuple[str, ...] = ("read",)
    risk_level: str = "low"
    signed_manifest_hash: str = ""
    approved_by_policy: bool = False
    active: bool = True
    quarantined: bool = False
    quarantine_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "endpoint_ref": self.endpoint_ref,
            "transport": self.transport,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "permissions": self.permissions,
            "risk_level": self.risk_level,
            "signed_manifest_hash": self.signed_manifest_hash,
            "approved_by_policy": self.approved_by_policy,
            "active": self.active,
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason,
        }


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    from_agent_id: str
    to_agent_id: str
    session_id: str
    message_type: str
    content_summary: str
    structured_payload: Mapping[str, Any] = field(default_factory=dict)
    citations: tuple[str, ...] = ()
    policy_tags: tuple[str, ...] = ("no_hidden_chain_of_thought",)
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "session_id": self.session_id,
            "message_type": self.message_type,
            "content_summary": self.content_summary,
            "structured_payload": dict(self.structured_payload),
            "citations": self.citations,
            "policy_tags": self.policy_tags,
            "created_at": self.created_at,
        }


def register_agent_identity(agent_id: str, *, display_name: str = "", description: str = "", genome_id: str = "", root: str | Path = ".") -> Mapping[str, Any]:
    network_agent_id = stable_id("network_agent", agent_id, genome_id, display_name or agent_id)
    identity = AgentNetworkIdentity(
        network_agent_id=network_agent_id,
        local_agent_id=agent_id,
        genome_id=genome_id,
        display_name=display_name or agent_id,
        description=description or "Policy-gated Flow Memory agent node.",
        skill_manifest_ref=f"artifacts/agent_internet/skills/{agent_id}.json",
        reputation_ref=f"artifacts/agent_internet/reputation/{agent_id}.json",
    )
    return _write_record(root, "identities", agent_id, identity.as_record())


def update_agent_identity(agent_id: str, updates: Mapping[str, Any], *, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_agent_identity(agent_id, root=root))
    record.update({key: value for key, value in updates.items() if key not in {"local_agent_id", "network_agent_id"}})
    record["updated_at"] = utc_now()
    return _write_record(root, "identities", agent_id, record)


def list_agent_identities(*, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    return _list_records(root, "identities")


def get_agent_identity(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "identities", agent_id)


def deactivate_agent_identity(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return update_agent_identity(agent_id, {"active": False}, root=root)


def publish_skill_manifest(agent_id: str, skills: Sequence[str | Mapping[str, Any]], *, root: str | Path = ".", domains: Sequence[str] = ()) -> Mapping[str, Any]:
    skill_records = tuple(_skill_record(agent_id, item) for item in skills)
    manifest_id = stable_id("skill_manifest", agent_id, "|".join(str(skill.get("skill_id", "")) for skill in skill_records))
    manifest = AgentSkillManifest(
        manifest_id=manifest_id,
        agent_id=agent_id,
        skills=skill_records,
        domains=tuple(_clean_tuple(domains)),
        preferred_tasks=tuple(str(item.get("name", item.get("category", "task"))) for item in skill_records),
        evidence_refs=(f"artifacts/agent_internet/identities/{agent_id}.json",),
    )
    return _write_record(root, "skills", agent_id, manifest.as_record())


def get_skill_manifest(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "skills", agent_id)


def list_skill_manifests(*, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    return _list_records(root, "skills")


def match_skills(
    requester_agent_id: str,
    task_description: str,
    *,
    required_skills: Sequence[str] = (),
    optional_skills: Sequence[str] = (),
    missing_skills: Sequence[str] = (),
    domain: str = "",
    collaboration_style: str = "approval_required",
    policy_constraints: Sequence[str] = ("approval_required", "no_raw_private_memory"),
    budget_policy: str = "dry_run_only",
    trust_minimum: float = 0.0,
    max_candidates: int = 5,
    root: str | Path = ".",
) -> Mapping[str, Any]:
    required = set(_clean_tuple(required_skills))
    optional = set(_clean_tuple(optional_skills))
    missing = set(_clean_tuple(missing_skills))
    identities = {item.get("local_agent_id"): item for item in list_agent_identities(root=root)}
    manifests = list_skill_manifests(root=root)
    ranked: list[Mapping[str, Any]] = []
    rejected: list[Mapping[str, Any]] = []
    breakdown: dict[str, Any] = {}
    for manifest in manifests:
        agent_id = str(manifest.get("agent_id", ""))
        if not agent_id or agent_id == requester_agent_id:
            continue
        identity = dict(identities.get(agent_id, {}))
        skill_names = {str(skill.get("category", skill.get("name", ""))).lower() for skill in manifest.get("skills", ())}
        skill_names.update(str(skill.get("name", "")).lower().replace(" ", "_") for skill in manifest.get("skills", ()))
        required_hit = len(required & skill_names)
        optional_hit = len(optional & skill_names)
        complementary_hit = len(missing & skill_names)
        policy_ok = all(item in tuple(manifest.get("safety_constraints", ())) or item == "approval_required" for item in policy_constraints)
        privacy_ok = dict(identity.get("privacy_policy", {})).get("private_memory_excluded") is not False
        dry_run_ok = budget_policy == "none" or str(identity.get("payment_capability", "none")) in {"none", "dry_run_x402", "simulated_invoice"}
        reputation = reputation_summary(agent_id, root=root).get("score", 0.7)
        score = round(required_hit * 0.32 + optional_hit * 0.12 + complementary_hit * 0.18 + float(reputation) * 0.22 + (0.08 if policy_ok else -0.2) + (0.04 if privacy_ok else -0.3) + (0.04 if dry_run_ok else -0.2), 4)
        candidate = {
            "agent_id": agent_id,
            "network_agent_id": identity.get("network_agent_id", ""),
            "display_name": identity.get("display_name", agent_id),
            "score": score,
            "skill_overlap": tuple(sorted(required & skill_names)),
            "optional_overlap": tuple(sorted(optional & skill_names)),
            "complementary_skills": tuple(sorted(missing & skill_names)),
            "reputation_score": reputation,
            "policy_compatible": policy_ok,
            "privacy_compatible": privacy_ok,
            "dry_run_payment_compatible": dry_run_ok,
        }
        breakdown[agent_id] = candidate
        if score < trust_minimum or not policy_ok or not privacy_ok:
            rejected.append({**candidate, "reason": "policy_or_trust_threshold"})
        else:
            ranked.append(candidate)
    ranked.sort(key=lambda item: (-float(item["score"]), str(item["agent_id"])))
    ranked = ranked[: max(1, int(max_candidates))]
    match = SkillMatchResult(
        match_id=stable_id("skill_match", requester_agent_id, task_description, tuple(required), tuple(optional), tuple(missing)),
        requester_agent_id=requester_agent_id,
        task_description=task_description,
        ranked_candidates=tuple(ranked),
        score_breakdown=breakdown,
        recommended_collaborator_ids=tuple(str(item["agent_id"]) for item in ranked[:3]),
        rejected_candidates=tuple(rejected),
        policy_warnings=() if ranked else ("no_policy_compatible_candidates",),
        explanation="Ranked by skill overlap, complementary skills, reputation, policy compatibility, privacy compatibility, and dry-run payment compatibility.",
    )
    record = match.as_record()
    _write_record(root, "matches", match.match_id, record)
    return record


def propose_collaboration(from_agent_id: str, to_agent_id: str, task: str, *, required_skills: Sequence[str] = (), root: str | Path = ".") -> Mapping[str, Any]:
    request_id = stable_id("collaboration_request", from_agent_id, to_agent_id, task, tuple(required_skills))
    workspace_id = stable_id("shared_workspace", request_id, from_agent_id, to_agent_id)
    request = CollaborationRequest(request_id, from_agent_id, to_agent_id, task, tuple(_clean_tuple(required_skills)), shared_workspace_id=workspace_id)
    request_record = request.as_record()
    _write_record(root, "collaborations/requests", request_id, request_record)
    session_id = stable_id("collaboration_session", request_id, workspace_id)
    project_id = stable_id("agent_project", task, from_agent_id, to_agent_id)
    session = CollaborationSession(
        session_id=session_id,
        agent_ids=(from_agent_id, to_agent_id),
        roles={from_agent_id: "requester", to_agent_id: "collaborator"},
        shared_workspace_id=workspace_id,
        task_id=stable_id("task", task),
        project_id=project_id,
        policy_state={"approval_required": True, "raw_private_memory_shared": False, "status": "proposed"},
        messages_summary=("Collaboration proposed through policy-gated Agent Internet.",),
    )
    workspace = SharedCognitiveWorkspace(
        workspace_id=workspace_id,
        project_id=project_id,
        participating_agent_ids=(from_agent_id, to_agent_id),
        task_context=task,
        predictions=({"summary": "Collaboration should improve task coverage if required skills match.", "confidence": 0.72},),
        policy_checks=({"check": "raw_private_memory", "allowed": False}, {"check": "approval_required", "allowed": True}),
        audit_events=({"event": "collaboration_proposed", "request_id": request_id},),
    )
    session_record = session.as_record()
    workspace_record = workspace.as_record()
    _write_record(root, "collaborations/sessions", session_id, session_record)
    _write_record(root, "workspaces", workspace_id, workspace_record)
    graph = project_graph(project_id, [from_agent_id, to_agent_id], tuple(required_skills), task, root=root)
    return {"ok": True, "request": request_record, "session": session_record, "workspace": workspace_record, "project_graph": graph}


def list_collaborations(*, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    return _list_records(root, "collaborations/sessions")


def get_collaboration(session_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "collaborations/sessions", session_id)


def get_workspace(workspace_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "workspaces", workspace_id)


def project_graph(project_id: str, agent_ids: Sequence[str], skills: Sequence[str], task: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    nodes = [{"id": project_id, "type": "project", "label": task}]
    edges: list[Mapping[str, Any]] = []
    for agent_id in _clean_tuple(agent_ids):
        nodes.append({"id": agent_id, "type": "agent", "label": agent_id})
        edges.append({"from": agent_id, "to": project_id, "type": "contributed_to"})
    for skill in _clean_tuple(skills):
        skill_id = f"skill:{skill}"
        nodes.append({"id": skill_id, "type": "skill", "label": skill})
        edges.append({"from": project_id, "to": skill_id, "type": "used_skill"})
    graph = ProjectGraph(stable_id("project_graph", project_id, tuple(agent_ids), tuple(skills)), project_id, tuple(nodes), tuple(edges)).as_record()
    _write_record(root, "project_graphs", project_id, graph)
    return graph


def contribute_knowledge(agent_id: str, title: str, summary: str, *, citations: Sequence[str] = (), privacy_mode: str = "private_only", root: str | Path = ".") -> Mapping[str, Any]:
    artifact = KnowledgeArtifact(stable_id("knowledge_artifact", agent_id, title, summary), agent_id, title, summary, tuple(_clean_tuple(citations)), privacy_mode=privacy_mode)
    return _write_record(root, "knowledge", artifact.artifact_id, artifact.as_record())


def add_reputation_event(agent_id: str, event_type: str, score_delta: float, reason: str, *, source_session_id: str = "", evidence_refs: Sequence[str] = (), root: str | Path = ".") -> Mapping[str, Any]:
    event = ReputationEvent(stable_id("reputation_event", agent_id, event_type, reason, score_delta), agent_id, event_type, source_session_id, score_delta, reason, tuple(_clean_tuple(evidence_refs)))
    _write_record(root, "reputation/events", event.event_id, event.as_record())
    summary = reputation_summary(agent_id, root=root)
    _write_record(root, "reputation", agent_id, summary)
    return event.as_record()


def reputation_summary(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    events = [record for record in _list_records(root, "reputation/events") if record.get("agent_id") == agent_id]
    base = 0.7
    score = max(0.0, min(1.0, base + sum(float(record.get("score_delta", 0.0) or 0.0) for record in events)))
    return {
        "agent_id": agent_id,
        "score": round(score, 4),
        "prediction_accuracy": round(min(1.0, score + 0.05), 4),
        "policy_compliance": 1.0,
        "collaboration_success": round(score, 4),
        "lesson_usefulness": round(score, 4),
        "citation_quality": round(max(0.0, score - 0.05), 4),
        "task_completion": round(score, 4),
        "dispute_rate": 0.0,
        "unsafe_recommendation_rate": 0.0,
        "validation_success": round(score, 4),
        "contribution_reuse": round(max(0.0, score - 0.1), 4),
        "event_count": len(events),
        "events": tuple(events),
    }


def simulate_payment_intent(from_agent_id: str, to_agent_id: str, resource: str, amount: float, *, currency: str = "LOCAL", root: str | Path = ".") -> Mapping[str, Any]:
    intent = PaymentIntent(stable_id("payment_intent", from_agent_id, to_agent_id, resource, amount, currency), from_agent_id, to_agent_id, resource, float(amount), currency=currency)
    record = intent.as_record()
    _write_record(root, "payment_intents", intent.intent_id, record)
    return record


def create_mcp_manifest(tool_id: str, name: str, description: str, endpoint_ref: str, *, permissions: Sequence[str] = ("read",), risk_level: str = "low", signed_manifest_hash: str = "", root: str | Path = ".") -> Mapping[str, Any]:
    manifest = validate_mcp_manifest(MCPToolManifest(tool_id, name, description, endpoint_ref, permissions=tuple(_clean_tuple(permissions)), risk_level=risk_level, signed_manifest_hash=signed_manifest_hash).as_record())
    _write_record(root, "mcp_manifests", tool_id, manifest)
    return manifest


def validate_mcp_manifest(record: Mapping[str, Any]) -> Mapping[str, Any]:
    text = " ".join(str(record.get(key, "")) for key in ("name", "description", "endpoint_ref")).lower()
    risky_permissions = {"write", "execute", "shell", "wallet", "broadcast", "private_memory"}
    permissions = {str(item).lower() for item in record.get("permissions", ())}
    poisoned = any(term in text for term in ("ignore policy", "bypass approval", "steal", "private key", "seed phrase"))
    risky = bool(permissions & risky_permissions) or str(record.get("risk_level", "low")) in {"high", "critical"}
    return {
        **dict(record),
        "approved_by_policy": not poisoned and not risky,
        "quarantined": poisoned,
        "quarantine_reason": "tool_descriptor_policy_violation" if poisoned else "",
    }


def list_mcp_manifests(*, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    records = _list_records(root, "mcp_manifests")
    if records:
        return records
    return (validate_mcp_manifest(MCPToolManifest("local-read-fixture", "Local fixture reader", "Read local sanitized dashboard fixtures.", "local://dashboard/mock-data", signed_manifest_hash=stable_id("manifest_hash", "local-read-fixture")).as_record()),)


def create_agent_message(from_agent_id: str, to_agent_id: str, session_id: str, message_type: str, content_summary: str, *, payload: Mapping[str, Any] | None = None, citations: Sequence[str] = (), root: str | Path = ".") -> Mapping[str, Any]:
    message = AgentMessage(stable_id("agent_message", from_agent_id, to_agent_id, session_id, message_type, content_summary), from_agent_id, to_agent_id, session_id, message_type, content_summary, dict(payload or {}), tuple(_clean_tuple(citations)))
    record = message.as_record()
    _write_record(root, "messages", message.message_id, record)
    return record


def erc8004_export(agent_id: str, *, out: str | Path | None = None, root: str | Path = ".") -> Mapping[str, Any]:
    identity = get_agent_identity(agent_id, root=root)
    manifest = get_skill_manifest(agent_id, root=root)
    reputation = reputation_summary(agent_id, root=root)
    payload = {
        "format": "flow-memory-erc8004-export-v0",
        "agent_id": agent_id,
        "identity_registry_adapter": {"mode": "export_only", "identity": identity},
        "reputation_registry_adapter": {"mode": "export_only", "reputation": reputation},
        "validation_registry_adapter": {"mode": "export_only", "skill_manifest_id": manifest.get("manifest_id"), "policy_gated": True},
        "no_onchain_call": True,
        "no_private_key": True,
        "no_broadcast": True,
        "created_at": utc_now(),
    }
    path = Path(out) if out else _dir(root, "erc8004") / f"{_safe(agent_id)}.json"
    if not path.is_absolute():
        path = Path(root).resolve() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "path": _rel(Path(root).resolve(), path), "export": payload}


def demo_network(root: str | Path = ".") -> Mapping[str, Any]:
    alpha = "internet-alpha"
    beta = "internet-beta"
    register_agent_identity(alpha, display_name="Mira", description="Research-builder node", root=root)
    register_agent_identity(beta, display_name="Loom Helper", description="Verification and dashboard node", root=root)
    publish_skill_manifest(alpha, ("research", "memory", "planning"), root=root)
    publish_skill_manifest(beta, ("coding", "verification", "visual_dashboard"), root=root)
    add_reputation_event(beta, "validation_success", 0.08, "Completed deterministic dashboard validation", root=root)
    match = match_skills(alpha, "build an agent skill matcher", required_skills=("coding", "verification"), optional_skills=("visual_dashboard",), missing_skills=("coding", "verification"), root=root)
    collaboration = propose_collaboration(alpha, beta, "build an agent skill matcher", required_skills=("coding", "verification"), root=root)
    payment = simulate_payment_intent(alpha, beta, "skill_match", 0.01, root=root)
    mcp = create_mcp_manifest("skill-manifest-reader", "Skill manifest reader", "Read sanitized local Agent Internet skill manifests.", "local://agent_internet/skills", signed_manifest_hash=stable_id("manifest_hash", "skill-manifest-reader"), root=root)
    erc = erc8004_export(beta, root=root)
    knowledge = contribute_knowledge(beta, "Skill matcher validation", "Matched by coding and verification without sharing private memory.", citations=("dashboard/src/mock-data/agent-internet-skill-network.json",), root=root)
    return {"ok": True, "agents": list_agent_identities(root=root), "skills": list_skill_manifests(root=root), "match": match, "collaboration": collaboration, "payment_intent": payment, "mcp_manifest": mcp, "erc8004_export": erc, "knowledge": knowledge}


def _skill_record(agent_id: str, item: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        name = str(item.get("name", item.get("category", "research")))
        category = str(item.get("category", name)).lower().replace(" ", "_")
        return AgentSkill(
            skill_id=str(item.get("skill_id", stable_id("agent_skill", agent_id, name, category))),
            name=name,
            description=str(item.get("description", f"{name} capability")),
            category=category,
            proficiency=float(item.get("proficiency", 0.72) or 0.72),
            confidence=float(item.get("confidence", 0.74) or 0.74),
            evidence_refs=tuple(_clean_tuple(item.get("evidence_refs", ()))),
            benchmark_refs=tuple(_clean_tuple(item.get("benchmark_refs", ()))),
            requires_approval=bool(item.get("requires_approval", True)),
            policy_tags=tuple(_clean_tuple(item.get("policy_tags", ("policy_gated",)))),
            cost_hint=str(item.get("cost_hint", "local")),
            dry_run_supported=bool(item.get("dry_run_supported", True)),
        ).as_record()
    category = str(item).strip().lower().replace(" ", "_") or "research"
    if category not in DEFAULT_SKILL_CATEGORIES:
        category = category.replace("-", "_")
    return AgentSkill(stable_id("agent_skill", agent_id, category), category.replace("_", " ").title(), f"Deterministic {category} capability.", category=category, proficiency=0.74, confidence=0.76).as_record()


def _clean_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = [value]
    else:
        raw = list(value)
    return tuple(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


def _dir(root: str | Path, name: str) -> Path:
    return Path(root).resolve() / DEFAULT_ROOT / name


def _write_record(root: str | Path, category: str, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    path = _dir(root, category) / f"{_safe(key)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "path": _rel(Path(root).resolve(), path), **record}


def _read_record(root: str | Path, category: str, key: str) -> Mapping[str, Any]:
    path = _dir(root, category) / f"{_safe(key)}.json"
    if not path.exists():
        raise KeyError(f"unknown Agent Internet {category} record: {key}")
    return json.loads(path.read_text(encoding="utf-8"))


def _list_records(root: str | Path, category: str) -> tuple[Mapping[str, Any], ...]:
    directory = _dir(root, category)
    if not directory.exists():
        return ()
    return tuple(json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json")))


def _safe(value: str) -> str:
    safe = "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("record key is required")
    return safe


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
