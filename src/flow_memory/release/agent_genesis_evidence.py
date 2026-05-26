"""Release evidence for Agent Genesis and the Network Learning Protocol."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.agent_genesis import (
    CreateAgentBirthRequest,
    birth_agent,
    create_consent,
    create_contribution,
    create_teaching_event,
    list_archetypes,
    list_boundaries,
    list_instincts,
    validate_contribution,
)
from flow_memory.agent_genesis.contribution import CONTRIBUTION_TYPES
from flow_memory.agent_genesis.stages import stage_record
from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import (
    GENESIS_CREATE_SCOPE,
    GENESIS_EXPORT_SCOPE,
    GENESIS_READ_SCOPE,
    GENESIS_TEACH_SCOPE,
    required_scopes_for,
)
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir


_OVERCLAIM_PATTERNS = (
    "is agi",
    "achieves agi",
    "artificial general intelligence",
    "is conscious",
    "has consciousness",
    "agents have emotions",
    "agent has emotions",
    "agents have desires",
    "agent has desires",
    "subjective desires",
    "grants unbounded autonomy",
    "production autonomous intelligence",
    "guaranteed future",
    "predicts arbitrary real-world future",
)

_FLOWLANG_GENESIS = """
agent Mira {
  genesis {
    archetype: "research-builder"
    purpose: "help me build and remember Flow Memory"
    instincts: ["careful", "curious", "builder", "memory_first"]
    boundaries: ["ask_before_risky_action", "never_share_private_memory", "never_spend_money"]
    consent_mode: "private_only"
    stage: "seed"
  }

  memory_seed {
    user_preferences: ["exact commands", "honest status", "visible proof"]
    project_context: ["Flow Memory is the Human Compute Network"]
    behavior_rules: ["do not overclaim", "ask before risky actions"]
  }

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
  }

  cognition {
    predictive_core_enabled: true
    prediction_error_learning: true
    memory_consolidation_enabled: true
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
"""


def agent_genesis_network_learning_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    """Return deterministic public-alpha evidence for Agent Genesis."""

    root_path = Path(root).resolve()
    with TemporaryDirectory() as tmp:
        request = CreateAgentBirthRequest(
            user_id="local-user",
            agent_name="Mira",
            archetype_id="research-builder",
            purpose="Help me build Flow Memory",
            instincts=("careful", "builder", "memory_first"),
            consent_mode="private_only",
        )
        birth = birth_agent(request, root=tmp)
        agent_id = str(birth["agent_id"])
        genome = dict(birth["agent_profile"].get("metadata", {}).get("agent_genome", {}))
        certificate = dict(birth["birth_certificate"])
        passport = dict(birth["passport"])
        mirror = dict(birth["mirror"])
        consent = create_consent(
            user_id="local-user",
            agent_id=agent_id,
            mode="sanitized_lessons",
        )
        contribution = create_contribution(
            agent_id=agent_id,
            user_id="local-user",
            source_record_id="lesson_demo",
            contribution_type="consolidated_lesson",
            consent=consent.as_record(),
            payload={
                "title": "Observable-state verification",
                "summary": "Check observable state before reporting success.",
                "domain": "dashboard",
                "tags": ("dashboard", "verification"),
                "recommended_future_action": "Verify served Mission Control HTML before reporting dashboard success.",
                "usefulness_score": 0.82,
                "raw_private_content": "private repo note must stay local",
                "token": "redacted",
            },
        )
        teaching = create_teaching_event(
            user_id="local-user",
            agent_id=agent_id,
            correction_type="correction",
            content="That was a stale dashboard process, not broken code.",
            lesson="Check port 4173 before assuming Mission Control is broken.",
            applies_to_tags=("dashboard", "mission-control"),
        )

    archetypes = list_archetypes()
    instincts = list_instincts()
    boundaries = list_boundaries()
    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    genesis_routes = {
        "GET /genesis/archetypes",
        "GET /genesis/instincts",
        "GET /genesis/boundaries",
        "POST /genesis/birth",
        "GET /genesis/agents/{agent_id}/passport",
        "GET /genesis/agents/{agent_id}/genome",
        "GET /genesis/agents/{agent_id}/mirror",
        "POST /genesis/agents/{agent_id}/teaching",
        "GET /genesis/contributions",
        "POST /genesis/contributions/export",
    }
    flow_profile = agent_profile_from_ir(parse_flowlang(_FLOWLANG_GENESIS))
    docs_text = _docs_text(root_path)
    no_overclaims = _no_overclaim_patterns(docs_text)
    dashboard_dev_server = root_path / "dashboard" / "scripts" / "dev-server.mjs"
    dashboard_fixture = root_path / "dashboard" / "src" / "mock-data" / "agent-genesis-onboarding.json"
    cli = root_path / "src" / "flow_memory" / "cli.py"
    evidence = {
        "agent_genesis_available": bool(birth.get("ok")),
        "archetypes_available": {str(item.get("archetype_id", "")) for item in archetypes} >= {
            "research-builder",
            "memory-scout",
            "launch-assistant",
            "market-observer",
            "personal-operator",
            "teacher-agent",
            "network-mentor",
        },
        "instincts_available": {str(item.get("instinct_id", "")) for item in instincts} >= {
            "careful",
            "curious",
            "builder",
            "memory_first",
            "cost_aware",
            "safety_first",
            "fast_mover",
            "teacher",
            "scout",
            "verifier",
        },
        "boundaries_available": {str(item.get("boundary_id", "")) for item in boundaries} >= {
            "ask_before_risky_action",
            "never_spend_money",
            "never_delete_without_approval",
            "never_share_private_memory",
            "local_only_by_default",
            "no_external_provider_calls",
            "no_live_settlement",
            "no_private_keys",
            "no_unapproved_tool_use",
        },
        "agent_genome_available": bool(genome.get("genome_id")) and genome.get("private_memory_excluded") is True,
        "memory_seed_available": bool(certificate.get("memory_seed_id")),
        "first_prediction_ceremony_available": bool(certificate.get("first_prediction", {}).get("prediction")),
        "agent_mirror_available": bool(mirror.get("lesson")) and bool(mirror.get("prediction")),
        "agent_passport_available": passport.get("stage") == "seed" and bool(passport.get("genome_id")),
        "agent_stages_available": stage_record("seed")["stage"] == "seed" and stage_record("mentor")["stage"] == "mentor",
        "network_learning_consent_available": consent.mode == "sanitized_lessons" and consent.raw_payload_allowed is False,
        "private_only_default": certificate.get("privacy", {}).get("mode") == "private_only" and certificate.get("network_learning_status") == "disabled",
        "sanitized_contribution_protocol_available": not validate_contribution(contribution) and contribution.validation_status == "accepted",
        "raw_private_payload_excluded": contribution.raw_payload_excluded is True and "raw_private_content" not in contribution.sanitized_payload,
        "human_teaching_events_available": teaching.teaching_event_id.startswith("teaching_event_") and teaching.privacy_mode == "private_only",
        "cli_genesis_available": _file_contains(cli, "def _genesis") and _file_contains(cli, "\"genesis\""),
        "api_genesis_available": genesis_routes.issubset(manifest_routes) and genesis_routes.issubset(registered_routes) and _scope_checks_ok(),
        "dashboard_genesis_available": dashboard_fixture.exists() and _file_contains(dashboard_dev_server, "Agent Genesis"),
        "mission_control_genesis_integration_available": _file_contains(dashboard_dev_server, "Agent Passport") and _file_contains(dashboard_dev_server, "Agent Mirror"),
        "flowlang_genesis_block_available": flow_profile.metadata.get("genesis", {}).get("archetype_id") == "research-builder" and bool(flow_profile.metadata.get("memory_seed", {}).get("user_preferences")),
        "no_download_required_for_first_agent_documented": "no download" in docs_text and "first agent" in docs_text,
        "optional_node_path_documented": "optional node" in docs_text or "node download is optional" in docs_text,
        "no_agi_overclaim_invariant": no_overclaims,
        "no_consciousness_overclaim_invariant": no_overclaims,
        "no_unbounded_autonomy_invariant": no_overclaims,
        "public_alpha_docs_updated": _docs_updated(root_path),
    }
    ok = all(evidence.values()) and contribution.raw_payload_excluded is True
    return {
        "ok": ok,
        **evidence,
        "birth": {key: birth[key] for key in ("agent_id", "birth_id", "genome_id", "memory_seed_id", "consent_id", "first_prediction", "mission_control_url")},
        "passport": passport,
        "mirror": mirror,
        "genome": genome,
        "consent_modes": ("private_only", "sanitized_lessons", "anonymous_benchmark_traces", "public_agent_genome", "compute_node_contributor"),
        "contribution_types": tuple(sorted(CONTRIBUTION_TYPES)),
        "sample_contribution": contribution.as_record(),
        "sample_teaching_event": teaching.as_record(),
        "api_routes": tuple(sorted(genesis_routes)),
        "docs_scanned": True,
        "raw_private_payload_excluded_from_sample": "raw_private_content" not in contribution.sanitized_payload,
        "safety_authority": "policy_engine_and_approval_gate",
        "network_learning_default": "private_only",
    }


def verify_agent_genesis_network_learning_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    if record.get("ok") is not True:
        blockers.append("agent_genesis_evidence_not_ok")
    for key in (
        "agent_genesis_available",
        "archetypes_available",
        "instincts_available",
        "boundaries_available",
        "agent_genome_available",
        "memory_seed_available",
        "first_prediction_ceremony_available",
        "agent_mirror_available",
        "agent_passport_available",
        "agent_stages_available",
        "network_learning_consent_available",
        "private_only_default",
        "sanitized_contribution_protocol_available",
        "raw_private_payload_excluded",
        "human_teaching_events_available",
        "cli_genesis_available",
        "api_genesis_available",
        "dashboard_genesis_available",
        "mission_control_genesis_integration_available",
        "flowlang_genesis_block_available",
        "no_download_required_for_first_agent_documented",
        "optional_node_path_documented",
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
        "no_unbounded_autonomy_invariant",
        "public_alpha_docs_updated",
    ):
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    contribution = dict(record.get("sample_contribution", {})) if isinstance(record.get("sample_contribution", {}), Mapping) else {}
    if contribution.get("raw_payload_excluded") is not True:
        blockers.append("raw_payload_not_excluded")
    if contribution.get("privacy_mode") == "private_only" and contribution.get("validation_status") != "private_only":
        blockers.append("private_only_contribution_not_blocked")
    return {"ok": not blockers, "blockers": tuple(blockers)}


def _scope_checks_ok() -> bool:
    return (
        required_scopes_for("GET", "/genesis/archetypes") == (GENESIS_READ_SCOPE,)
        and required_scopes_for("POST", "/genesis/birth") == (GENESIS_CREATE_SCOPE,)
        and required_scopes_for("POST", "/genesis/agents/demo/teaching") == (GENESIS_TEACH_SCOPE,)
        and required_scopes_for("POST", "/genesis/contributions/export") == (GENESIS_EXPORT_SCOPE,)
    )


def _docs_text(root: Path) -> str:
    texts: list[str] = []
    for relative in (
        "README.md",
        "docs/AGENT_GENESIS.md",
        "docs/NETWORK_LEARNING_PROTOCOL.md",
        "docs/AGENT_GENOMES.md",
        "docs/PREDICTIVE_COGNITIVE_CORE.md",
        "docs/PREDICTIVE_LEARNING_BENCHMARK.md",
        "docs/NEURAL_LIVE_AGENTS.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "docs/PUBLIC_ALPHA_READINESS.md",
        "docs/START_HERE.md",
        "BUILD_REPORT.md",
        "FLOW_MEMORY_STATUS.md",
    ):
        path = root / relative
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(texts).lower()


def _no_overclaim_patterns(text: str) -> bool:
    lowered = text.lower()
    return not any(pattern in lowered for pattern in _OVERCLAIM_PATTERNS)


def _docs_updated(root: Path) -> bool:
    required = (
        root / "docs" / "AGENT_GENESIS.md",
        root / "docs" / "NETWORK_LEARNING_PROTOCOL.md",
        root / "docs" / "AGENT_GENOMES.md",
        root / "docs" / "START_HERE.md",
        root / "docs" / "PUBLIC_ALPHA_READINESS.md",
        root / "docs" / "NEURAL_LIVE_AGENTS.md",
        root / "docs" / "MISSION_CONTROL_QUICKSTART.md",
        root / "README.md",
        root / "BUILD_REPORT.md",
        root / "FLOW_MEMORY_STATUS.md",
    )
    if not all(path.exists() for path in required):
        return False
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required).lower()
    return "agent genesis" in text and "network learning" in text and "private only" in text


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="ignore")
