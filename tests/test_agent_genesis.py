import json
import subprocess
import sys

from flow_memory.agent_genesis import (
    CreateAgentBirthRequest,
    birth_agent,
    create_consent,
    create_contribution,
    create_genome,
    create_memory_seed,
    create_teaching_event,
    genome_to_agent_profile,
    list_archetypes,
    list_boundaries,
    list_instincts,
    validate_contribution,
    write_teaching_event,
)
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
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
from flow_memory.release.agent_genesis_evidence import (
    agent_genesis_network_learning_evidence,
    verify_agent_genesis_network_learning_evidence,
)
from flow_memory.release.readiness import decide_release_readiness


FLOWLANG_GENESIS = '''
agent Mira {
  genesis {
    archetype: "research-builder"
    purpose: "help me build and remember Flow Memory"
    instincts: ["careful", "builder", "memory_first"]
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
'''


def test_genesis_registries_include_public_alpha_defaults():
    archetypes = {item["archetype_id"] for item in list_archetypes()}
    instincts = {item["instinct_id"] for item in list_instincts()}
    boundaries = {item["boundary_id"] for item in list_boundaries()}

    assert {"research-builder", "memory-scout", "network-mentor"}.issubset(archetypes)
    assert {"careful", "builder", "memory_first", "verifier"}.issubset(instincts)
    assert {"never_spend_money", "never_share_private_memory", "no_private_keys"}.issubset(boundaries)


def test_genome_memory_seed_and_profile_are_private_by_default(tmp_path):
    seed = create_memory_seed(
        agent_id="agent-test",
        user_preferences=("exact commands",),
        project_context=("Flow Memory",),
        behavior_rules=("ask before risky actions",),
        raw_private_content="private note",
    )
    consent = create_consent(user_id="local-user", agent_id="agent-test", mode="private_only")
    genome = create_genome(
        agent_id="agent-test",
        archetype_id="research-builder",
        purpose="Help me build Flow Memory",
        instincts=("careful", "builder"),
        boundaries=("ask_before_risky_action", "never_share_private_memory", "never_spend_money"),
        neural_profile={"enabled": True, "backend": "tiny_torch", "live_mode": True, "policy_fallback": "fail_closed"},
        cognition_profile={"predictive_core_enabled": True, "memory_consolidation_enabled": True, "policy_fallback": "fail_closed"},
        memory_profile={"private_memory": True, "memory_seed_id": seed.seed_id},
        privacy_profile={"consent_mode": consent.mode, "raw_payload_allowed": consent.raw_payload_allowed, "private_memory_allowed": consent.private_memory_allowed},
        contribution_profile={"network_learning": consent.mode, "raw_private_payload_excluded": True},
    )
    profile = genome_to_agent_profile(genome)

    assert seed.raw_private_content == "private note"
    assert seed.as_record()["raw_private_content_shared"] is False
    assert consent.mode == "private_only"
    assert consent.raw_payload_allowed is False
    assert genome.private_memory_excluded is True
    assert profile.autonomy_mode == "supervised"
    assert profile.metadata["agent_genome"]["privacy_profile"]["raw_payload_allowed"] is False


def test_network_contribution_sanitizes_private_payloads():
    consent = create_consent(user_id="local-user", agent_id="agent-test", mode="sanitized_lessons")
    contribution = create_contribution(
        agent_id="agent-test",
        user_id="local-user",
        source_record_id="lesson-1",
        contribution_type="consolidated_lesson",
        consent=consent.as_record(),
        payload={
            "title": "Dashboard stale process",
            "summary": "Check port 4173 before assuming code failed.",
            "domain": "dashboard",
            "recommended_future_action": "Verify served HTML.",
            "raw_private_content": "do not share",
            "token": "secret",
        },
    )

    assert contribution.validation_status == "accepted"
    assert contribution.raw_payload_excluded is True
    assert contribution.sanitized_payload["raw_private_payload_excluded"] is True
    assert "raw_private_content" not in contribution.sanitized_payload
    assert "token" not in contribution.sanitized_payload
    assert validate_contribution(contribution) == ()


def test_agent_birth_certificate_mirror_and_passport(tmp_path):
    result = birth_agent(
        CreateAgentBirthRequest(
            user_id="local-user",
            agent_name="Mira",
            archetype_id="research-builder",
            purpose="Help me build Flow Memory",
            instincts=("careful", "builder"),
            consent_mode="private_only",
        ),
        root=tmp_path,
    )

    assert result["ok"] is True
    assert result["birth_certificate"]["privacy"]["mode"] == "private_only"
    assert result["first_prediction"]["policy"] == "supervised; approval required"
    assert result["mirror"]["memory_written"] is True
    assert result["passport"]["stage"] == "seed"
    assert result["birth_certificate"]["network_learning_status"] == "disabled"


def test_teaching_event_writes_private_lesson(tmp_path):
    event = create_teaching_event(
        user_id="local-user",
        agent_id="agent-test",
        correction_type="correction",
        lesson="Check port 4173 before assuming Mission Control is broken.",
        applies_to_tags=("dashboard",),
    )
    written = write_teaching_event(event, root=tmp_path)

    assert written["ok"] is True
    assert written["record"]["privacy_mode"] == "private_only"
    assert written["private_lesson"]["recommended_future_action"] == event.lesson
    assert "human-teaching" in written["private_lesson"]["tags"]


def test_flowlang_genesis_block_converts_to_agent_profile():
    profile = agent_profile_from_ir(parse_flowlang(FLOWLANG_GENESIS))

    assert profile.metadata["genesis"]["archetype_id"] == "research-builder"
    assert profile.metadata["genesis"]["consent_mode"] == "private_only"
    assert profile.metadata["memory_seed"]["user_preferences"] == ["exact commands", "honest status", "visible proof"]
    assert profile.neural_config["backend"] == "tiny_torch"
    assert profile.cognition_config["memory_consolidation_enabled"] is True


def test_genesis_api_routes_and_scopes_are_enforced():
    router = create_default_router()
    registry = router.dispatch("GET", "/genesis/archetypes")
    born = router.dispatch(
        "POST",
        "/genesis/birth",
        {"user_id": "api-user", "agent_name": "Mira", "archetype_id": "memory-scout", "purpose": "Track lessons"},
    )

    assert registry["ok"] is True
    assert born["ok"] is True
    assert router.dispatch("GET", f"/genesis/agents/{born['agent_id']}/passport")["passport"]["stage"] == "seed"
    assert required_scopes_for("GET", "/genesis/archetypes") == (GENESIS_READ_SCOPE,)
    assert required_scopes_for("POST", "/genesis/birth") == (GENESIS_CREATE_SCOPE,)
    assert required_scopes_for("POST", "/genesis/agents/demo/teaching") == (GENESIS_TEACH_SCOPE,)
    assert required_scopes_for("POST", "/genesis/contributions/export") == (GENESIS_EXPORT_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("POST", "/genesis/birth", {"x-flow-memory-scopes": GENESIS_READ_SCOPE}, json.dumps({"agent_name": "Denied"}).encode())
    allowed = gateway.handle(
        "POST",
        "/genesis/birth",
        {"x-flow-memory-scopes": GENESIS_CREATE_SCOPE},
        json.dumps({"user_id": "api-user", "agent_name": "Allowed", "archetype_id": "research-builder"}).encode(),
    )

    assert denied.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["ok"] is True


def test_genesis_cli_registry_command_returns_json():
    result = subprocess.run(
        [sys.executable, "-m", "flow_memory", "genesis", "archetypes", "list", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["count"] >= 7


def test_mission_control_genesis_fixture_is_valid():
    with open("dashboard/src/mock-data/agent-genesis-onboarding.json", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["ok"] is True
    assert payload["label"] == "Agent Genesis"
    assert payload["learning_consent"]["default_mode"] == "private_only"
    assert payload["learning_consent"]["raw_private_payload_excluded"] is True
    assert payload["summary"]["no_download_required_for_first_agent"] is True
    assert "Node download is optional" in payload["summary"]["optional_node_path"]


def test_agent_genesis_release_evidence_fields():
    evidence = agent_genesis_network_learning_evidence(".")
    decision = verify_agent_genesis_network_learning_evidence(evidence)

    assert evidence["agent_genesis_available"] is True
    assert evidence["private_only_default"] is True
    assert evidence["raw_private_payload_excluded"] is True
    assert evidence["api_genesis_available"] is True
    assert evidence["dashboard_genesis_available"] is True
    assert decision["ok"] is True


def test_release_decision_public_alpha_genesis_target_is_known():
    decision = decide_release_readiness(".", target="public-alpha-genesis")

    assert decision.target == "public-alpha-genesis"
    assert "agent_genesis_network_learning" in decision.required_evidence
