"""Flow Memory Agent Builder browser agent-builder domain contract.

Agent Builder composes existing Agent Genesis, Agent Internet, BYOK, wallet, on-chain
simulation, and x402 dry-run seams into one safe browser-facing assembly plan.
The first-agent path remains no-wallet, no-key, no-funds, private by default,
and policy-gated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_genesis import birth_agent, list_archetypes, list_boundaries, list_instincts
from flow_memory.agent_internet import match_skills, publish_skill_manifest, register_agent_identity
from flow_memory.capability_upgrades import (
    bind_wallet_identity,
    capability_summary,
    create_credential_binding,
    prepare_onchain_upgrade,
    prepare_x402_payment_route,
    provider_registry,
    simulate_byok_inference_intent,
    simulate_onchain_upgrade,
    wallet_status,
    x402_adapter_status,
)
from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_USER_ID = "local-user"
DEFAULT_AGENT_NAME = "Mira"
DEFAULT_PURPOSE = "Help me build, remember, and verify Flow Memory work."
DEFAULT_WALLET_ADDRESS = "0x0000000000000000000000000000000000000000"

CAPABILITY_CARDS: tuple[Mapping[str, Any], ...] = (
    {
        "capability_id": "local_neural_runtime",
        "label": "Local neural runtime",
        "status": "enabled_by_default",
        "default_state": "on",
        "safety_note": "Runs locally with tiny_torch-safe defaults for public alpha.",
        "optional": False,
        "requires_approval": False,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": False,
    },
    {
        "capability_id": "predictive_cognition",
        "label": "Predictive cognition",
        "status": "enabled_by_default",
        "default_state": "on",
        "safety_note": "Predicts, compares, and learns from local observed outcomes.",
        "optional": False,
        "requires_approval": False,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": False,
    },
    {
        "capability_id": "agent_internet_identity",
        "label": "Agent Internet identity",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Publishes identity metadata without raw private memory.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "skill_manifest",
        "label": "Skill manifest",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Lists policy-gated skills for local matching.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "skill_matcher",
        "label": "Skill matcher",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Ranks collaborators by skills, policy, privacy, and reputation.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "byok_model_key",
        "label": "BYOK model key",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Stores secret references and fingerprints only; no raw key artifacts.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": False,
        "requires_api_key": True,
        "dry_run_only": True,
    },
    {
        "capability_id": "wallet_identity",
        "label": "Wallet identity",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Address binding only; no private keys or seed phrases.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": True,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "onchain_dry_run",
        "label": "On-chain dry run",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Prepare and simulate only; relay stays disabled by default.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": True,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "x402_dry_run_route",
        "label": "x402 dry-run route",
        "status": "optional_after_birth",
        "default_state": "off",
        "safety_note": "Base Sepolia route metadata can be prepared without settlement.",
        "optional": True,
        "requires_approval": True,
        "requires_wallet": True,
        "requires_api_key": False,
        "dry_run_only": True,
    },
    {
        "capability_id": "emergency_stop",
        "label": "Emergency stop",
        "status": "available_by_default",
        "default_state": "on",
        "safety_note": "Disables optional upgrade use and future execution modes.",
        "optional": False,
        "requires_approval": False,
        "requires_wallet": False,
        "requires_api_key": False,
        "dry_run_only": False,
    },
)


@dataclass(frozen=True)
class AgentBuilderAssemblyPlan:
    agent_builder_id: str
    user_id: str
    agent_name: str
    archetype_id: str
    purpose: str
    instincts: tuple[str, ...]
    boundaries: tuple[str, ...]
    memory_seed_summary: Mapping[str, Any]
    consent_mode: str = "private_only"
    first_agent_mode: bool = True
    selected_model_mode: str = "local_runtime"
    neural_enabled: bool = True
    cognition_enabled: bool = True
    motivation_enabled: bool = True
    agent_internet_enabled: bool = False
    skill_manifest_enabled: bool = False
    collaboration_enabled: bool = False
    byok_upgrade_requested: bool = False
    wallet_upgrade_requested: bool = False
    onchain_dry_run_requested: bool = False
    x402_dry_run_requested: bool = False
    emergency_stop_enabled: bool = True
    policy_summary: Mapping[str, Any] = field(default_factory=dict)
    privacy_summary: Mapping[str, Any] = field(default_factory=dict)
    expected_birth_result: Mapping[str, Any] = field(default_factory=dict)
    mission_control_url: str = "/mission-control#agent-builder"
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "agent_builder_id": self.agent_builder_id,
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "archetype_id": self.archetype_id,
            "purpose": self.purpose,
            "instincts": self.instincts,
            "boundaries": self.boundaries,
            "memory_seed_summary": dict(self.memory_seed_summary),
            "consent_mode": self.consent_mode,
            "first_agent_mode": self.first_agent_mode,
            "selected_model_mode": self.selected_model_mode,
            "neural_enabled": self.neural_enabled,
            "cognition_enabled": self.cognition_enabled,
            "motivation_enabled": self.motivation_enabled,
            "agent_internet_enabled": self.agent_internet_enabled,
            "skill_manifest_enabled": self.skill_manifest_enabled,
            "collaboration_enabled": self.collaboration_enabled,
            "byok_upgrade_requested": self.byok_upgrade_requested,
            "wallet_upgrade_requested": self.wallet_upgrade_requested,
            "onchain_dry_run_requested": self.onchain_dry_run_requested,
            "x402_dry_run_requested": self.x402_dry_run_requested,
            "emergency_stop_enabled": self.emergency_stop_enabled,
            "policy_summary": dict(self.policy_summary),
            "privacy_summary": dict(self.privacy_summary),
            "expected_birth_result": dict(self.expected_birth_result),
            "mission_control_url": self.mission_control_url,
            "created_at": self.created_at,
        }


def agent_builder_defaults() -> Mapping[str, Any]:
    return {
        "ok": True,
        "route": "/agents/new",
        "first_agent_mode": True,
        "simple_mode_default": True,
        "first_agent_requires_wallet": False,
        "first_agent_requires_api_key": False,
        "first_agent_requires_funds": False,
        "private_default": True,
        "network_learning_opt_in": True,
        "selected_model_mode_default": "local_runtime",
        "archetypes": list_archetypes(),
        "instincts": list_instincts(),
        "boundaries": list_boundaries(),
        "providers": provider_registry(),
        "capability_cards": CAPABILITY_CARDS,
        "x402": x402_adapter_status(),
        "modes": (
            {"mode_id": "simple", "label": "Simple", "default": True, "wallet_required": False, "api_key_required": False, "funds_required": False},
            {"mode_id": "advanced", "label": "Advanced", "default": False, "wallet_required": False, "api_key_required": False, "funds_required": False, "optional_upgrades_only": True},
        ),
    }


def create_agent_builder_assembly_plan(payload: Mapping[str, Any] | None = None, *, root: str | Path = ".") -> Mapping[str, Any]:
    data = dict(payload or {})
    user_id = str(data.get("user_id", data.get("user", DEFAULT_USER_ID)) or DEFAULT_USER_ID)
    agent_name = str(data.get("agent_name", data.get("name", DEFAULT_AGENT_NAME)) or DEFAULT_AGENT_NAME)
    archetype_id = str(data.get("archetype_id", data.get("archetype", "research-builder")) or "research-builder")
    purpose = str(data.get("purpose", DEFAULT_PURPOSE) or DEFAULT_PURPOSE)
    instincts = _tuple(data.get("instincts", ("careful", "builder", "memory_first")))
    boundaries = _tuple(data.get("boundaries", ("ask_before_risky_action", "never_spend_money", "never_share_private_memory", "local_only_by_default")))
    consent_mode = str(data.get("consent_mode", data.get("consent", "private_only")) or "private_only")
    selected_model_mode = str(data.get("selected_model_mode", data.get("model_mode", "local_runtime")) or "local_runtime")
    memory_seed = _memory_seed_summary(data.get("memory_seed", {}))
    first_agent_mode = _bool(data.get("first_agent_mode", True))
    byok_requested = _bool(data.get("byok_upgrade_requested", data.get("byok", False))) and not first_agent_mode
    wallet_requested = _bool(data.get("wallet_upgrade_requested", data.get("wallet", False))) and not first_agent_mode
    onchain_requested = _bool(data.get("onchain_dry_run_requested", data.get("onchain_dry_run", False))) and not first_agent_mode
    x402_requested = _bool(data.get("x402_dry_run_requested", data.get("x402", False))) and not first_agent_mode
    agent_internet_enabled = _bool(data.get("agent_internet_enabled", data.get("agent_internet", False))) and not first_agent_mode
    skill_manifest_enabled = _bool(data.get("skill_manifest_enabled", data.get("skill_manifest", False))) and not first_agent_mode
    collaboration_enabled = _bool(data.get("collaboration_enabled", data.get("collaboration", False))) and not first_agent_mode
    plan = AgentBuilderAssemblyPlan(
        agent_builder_id=stable_id("agent-builder", user_id, agent_name, archetype_id, purpose, tuple(instincts), tuple(boundaries), consent_mode, selected_model_mode),
        user_id=user_id,
        agent_name=agent_name,
        archetype_id=archetype_id,
        purpose=purpose,
        instincts=instincts,
        boundaries=boundaries,
        memory_seed_summary=memory_seed,
        consent_mode=consent_mode,
        first_agent_mode=first_agent_mode,
        selected_model_mode=selected_model_mode if selected_model_mode in {"local_runtime", "byok_reference", "hosted_stub"} else "local_runtime",
        neural_enabled=_bool(data.get("neural_enabled", True)),
        cognition_enabled=_bool(data.get("cognition_enabled", True)),
        motivation_enabled=_bool(data.get("motivation_enabled", True)),
        agent_internet_enabled=agent_internet_enabled,
        skill_manifest_enabled=skill_manifest_enabled,
        collaboration_enabled=collaboration_enabled,
        byok_upgrade_requested=byok_requested,
        wallet_upgrade_requested=wallet_requested,
        onchain_dry_run_requested=onchain_requested,
        x402_dry_run_requested=x402_requested,
        emergency_stop_enabled=_bool(data.get("emergency_stop_enabled", True)),
        policy_summary={"autonomy": "supervised", "approval_required": True, "policy_engine_authoritative": True, "approval_gate_authoritative": True},
        privacy_summary={"mode": consent_mode, "private_memory_default": True, "raw_private_memory_shared": False, "network_learning_opt_in": consent_mode != "private_only"},
        expected_birth_result={"genome": True, "memory_seed": True, "consent": True, "passport": True, "mirror": True, "first_prediction": True},
        mission_control_url=f"/mission-control#agent-builder-{stable_id('agent_builder_agent_ref', user_id, agent_name, purpose)}",
    )
    record = plan.as_record()
    return {"ok": True, "plan": record, "agent_builder_id": plan.agent_builder_id, "artifact_preview": f"artifacts/agents/new/plans/{plan.agent_builder_id}.json"}


def birth_agent_from_builder(payload: Mapping[str, Any], *, root: str | Path = ".") -> Mapping[str, Any]:
    plan_payload = create_agent_builder_assembly_plan(payload, root=root)
    plan = dict(plan_payload["plan"])
    birth = birth_agent(
        {
            "user_id": plan["user_id"],
            "agent_name": plan["agent_name"],
            "archetype_id": plan["archetype_id"],
            "purpose": plan["purpose"],
            "instincts": tuple(plan.get("instincts", ())),
            "boundaries": tuple(plan.get("boundaries", ())),
            "memory_seed": _memory_seed_from_summary(plan.get("memory_seed_summary", {})),
            "consent_mode": plan.get("consent_mode", "private_only"),
            "launch_immediately": False,
            "open_mission_control": True,
        },
        root=root,
    )
    agent_id = str(birth.get("agent_id", ""))
    internet = publish_agent_builder_identity(agent_id, plan, root=root) if plan.get("agent_internet_enabled") else {"ok": True, "enabled": False}
    upgrades = simulate_agent_builder_upgrades(
        agent_id,
        byok=bool(plan.get("byok_upgrade_requested")),
        wallet=bool(plan.get("wallet_upgrade_requested")),
        onchain_dry_run=bool(plan.get("onchain_dry_run_requested")),
        x402=bool(plan.get("x402_dry_run_requested")),
        root=root,
    )
    return {
        "ok": True,
        "agent_builder_id": plan["agent_builder_id"],
        "plan": plan,
        "birth": birth,
        "agent_id": agent_id,
        "mission_control_url": f"/mission-control#agent-builder-{agent_id}",
        "internet": internet,
        "upgrades": upgrades,
        "first_agent_requires_wallet": False,
        "first_agent_requires_api_key": False,
        "first_agent_requires_funds": False,
        "private_default": True,
        "no_private_key_required": True,
        "no_seed_phrase_required": True,
        "no_funds_moved": True,
        "no_broadcast": True,
    }


def publish_agent_builder_identity(agent_id: str, plan: Mapping[str, Any] | None = None, *, root: str | Path = ".") -> Mapping[str, Any]:
    plan = dict(plan or {})
    identity = register_agent_identity(agent_id, display_name=str(plan.get("agent_name", agent_id)), description=str(plan.get("purpose", "Agent Builder-created Flow Memory agent.")), genome_id=str(plan.get("genome_id", "")), root=root)
    skills = tuple(plan.get("skills", ()) or ("research", "coding", "memory", "verification"))
    manifest = publish_skill_manifest(agent_id, skills, root=root, domains=("flow_memory", "agent_builder"))
    _ensure_helper_agents(root=root)
    match = match_skills(agent_id, "assemble a Flow Memory browser agent", required_skills=("coding", "verification"), optional_skills=("visual_dashboard", "memory"), missing_skills=("safety_review",), root=root)
    return {"ok": True, "enabled": True, "identity": identity, "skill_manifest": manifest, "skill_match": match}


def simulate_agent_builder_upgrades(agent_id: str, *, byok: bool = False, wallet: bool = False, onchain_dry_run: bool = False, x402: bool = False, root: str | Path = ".") -> Mapping[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "agent_id": agent_id,
        "requested": {"byok": byok, "wallet": wallet, "onchain_dry_run": onchain_dry_run, "x402": x402},
        "first_agent_requires_wallet": False,
        "first_agent_requires_api_key": False,
        "first_agent_requires_funds": False,
        "no_private_key_required": True,
        "no_seed_phrase_required": True,
        "no_funds_moved": True,
        "no_broadcast": True,
    }
    credential: Mapping[str, Any] = {}
    if byok:
        credential = create_credential_binding(agent_id, "openai", "env:OPENAI_API_KEY", budget_cap=5.0, root=root)
        result["byok"] = {"credential": credential, "intent": simulate_byok_inference_intent(agent_id, "openai", "gpt-4.1-mini", "Agent Builder simulated research", credential_id=str(credential.get("credential_id", "")), root=root)}
    if wallet or onchain_dry_run or x402:
        result["wallet"] = bind_wallet_identity(agent_id, "base_sepolia", DEFAULT_WALLET_ADDRESS, root=root)
    else:
        result["wallet"] = wallet_status(agent_id, root=root)
    if onchain_dry_run:
        prepared = prepare_onchain_upgrade(agent_id, "base_sepolia", "register_agent", root=root)
        result["onchain"] = {"prepared": prepared, "simulation": simulate_onchain_upgrade(str(prepared["intent_id"]), root=root)}
    if x402:
        result["x402"] = prepare_x402_payment_route(agent_id, "agent_builder_skill_match", "0.001", DEFAULT_WALLET_ADDRESS, live_requested=True, root=root)
    result["capability_summary"] = capability_summary(agent_id, root=root)
    return result


def _ensure_helper_agents(*, root: str | Path = ".") -> None:
    helpers = (
        ("agent-builder-helper-verifier", "Agent Builder Verifier", ("verification", "safety_review", "documentation")),
        ("agent-builder-helper-visual", "Agent Builder Visual Builder", ("visual_dashboard", "coding", "memory")),
    )
    for agent_id, name, skills in helpers:
        try:
            register_agent_identity(agent_id, display_name=name, description="Local Agent Builder helper agent fixture.", root=root)
        except Exception:
            pass
        try:
            publish_skill_manifest(agent_id, skills, root=root, domains=("agent_builder", "dashboard"))
        except Exception:
            pass


def _memory_seed_summary(value: Any) -> Mapping[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    user_preferences = _tuple(source.get("user_preferences", ("exact commands", "honest status", "visible proof")))
    project_context = _tuple(source.get("project_context", ("Flow Memory is the Human Compute Network",)))
    behavior_rules = _tuple(source.get("behavior_rules", ("do not overclaim", "ask before risky actions", "verify outcomes")))
    return {
        "user_preferences": user_preferences,
        "project_context": project_context,
        "behavior_rules": behavior_rules,
        "initial_lessons": _tuple(source.get("initial_lessons", ())),
        "raw_private_content_excluded_from_network": True,
        "summary": "; ".join((*user_preferences[:2], *project_context[:1]))[:300],
    }


def _memory_seed_from_summary(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "user_preferences": tuple(summary.get("user_preferences", ())),
        "project_context": tuple(summary.get("project_context", ())),
        "behavior_rules": tuple(summary.get("behavior_rules", ())),
        "initial_lessons": tuple(summary.get("initial_lessons", ())),
    }


def _tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value if str(item).strip())
    return ()


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)
