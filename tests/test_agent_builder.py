import json
import os
import subprocess
import sys
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import AGENT_BUILDER_CREATE_SCOPE, AGENT_BUILDER_READ_SCOPE, AGENT_BUILDER_SIMULATE_SCOPE, required_scopes_for
from flow_memory.agent_builder import birth_agent_from_builder, create_agent_builder_assembly_plan, agent_builder_defaults, simulate_agent_builder_upgrades
from flow_memory.release.agent_builder_evidence import agent_builder_evidence, verify_agent_builder_evidence
from flow_memory.release.readiness import decide_release_readiness


REPO_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_SRC) if not existing else str(REPO_SRC) + os.pathsep + existing
    return env


def test_agent_builder_defaults_and_plan_are_simple_safe(tmp_path):
    defaults = agent_builder_defaults()
    plan = create_agent_builder_assembly_plan({"name": "Mira", "purpose": "Help me build Flow Memory"}, root=tmp_path)["plan"]

    assert defaults["route"] == "/agents/new"
    assert defaults["simple_mode_default"] is True
    assert defaults["first_agent_requires_wallet"] is False
    assert defaults["first_agent_requires_api_key"] is False
    assert defaults["first_agent_requires_funds"] is False
    assert defaults["private_default"] is True
    assert defaults["network_learning_opt_in"] is True
    assert len(defaults["capability_cards"]) >= 10
    assert plan["first_agent_mode"] is True
    assert plan["selected_model_mode"] == "local_runtime"
    assert plan["consent_mode"] == "private_only"
    assert plan["byok_upgrade_requested"] is False
    assert plan["wallet_upgrade_requested"] is False
    assert plan["onchain_dry_run_requested"] is False
    assert plan["x402_dry_run_requested"] is False


def test_agent_builder_birth_wrapper_and_optional_upgrade_simulation(tmp_path):
    birth = birth_agent_from_builder({"name": "Mira", "purpose": "Help me build Flow Memory"}, root=tmp_path)
    upgrades = simulate_agent_builder_upgrades(birth["agent_id"], byok=True, wallet=True, onchain_dry_run=True, x402=True, root=tmp_path)

    assert birth["ok"] is True
    assert birth["agent_id"].startswith("genesis_agent_")
    assert birth["first_agent_requires_wallet"] is False
    assert birth["first_agent_requires_api_key"] is False
    assert birth["private_default"] is True
    assert birth["no_private_key_required"] is True
    assert birth["no_broadcast"] is True
    assert upgrades["ok"] is True
    assert upgrades["byok"]["credential"]["raw_secret_persisted"] is False
    assert upgrades["wallet"]["network_name"] == "base_sepolia"
    assert upgrades["onchain"]["simulation"]["simulation_result"]["no_broadcast"] is True
    assert upgrades["x402"]["settlement_enabled"] is False
    assert upgrades["no_funds_moved"] is True


def test_agent_builder_agent_internet_publish_and_skill_match(tmp_path):
    birth = birth_agent_from_builder(
        {
            "name": "NetworkMira",
            "purpose": "Find collaborators for a Flow Memory dashboard",
            "first_agent_mode": False,
            "agent_internet_enabled": True,
            "skill_manifest_enabled": True,
            "collaboration_enabled": True,
        },
        root=tmp_path,
    )

    assert birth["internet"]["enabled"] is True
    assert birth["internet"]["skill_manifest"]["ok"] is True
    assert birth["internet"]["skill_match"]["ranked_candidates"]
    assert birth["internet"]["skill_match"]["recommended_collaborator_ids"]
    assert birth["upgrades"]["requested"] == {"byok": False, "wallet": False, "onchain_dry_run": False, "x402": False}


def test_agent_builder_api_routes_and_scopes_are_enforced():
    router = create_default_router()
    defaults = router.dispatch("GET", "/agent-builder/defaults")
    plan = router.dispatch("POST", "/agent-builder/assembly-plan", {"name": "ApiMira", "purpose": "Plan Agent Builder"})
    birth = router.dispatch("POST", "/agent-builder/birth", {"name": "ApiMira", "purpose": "Birth Agent Builder"})
    upgrades = router.dispatch("POST", "/agent-builder/simulate-upgrades", {"agent_id": birth["agent_id"], "byok": True, "wallet": True, "onchain_dry_run": True})

    assert defaults["ok"] is True
    assert plan["plan"]["first_agent_mode"] is True
    assert birth["agent_id"].startswith("genesis_agent_")
    assert upgrades["ok"] is True
    assert required_scopes_for("GET", "/agent-builder/defaults") == (AGENT_BUILDER_READ_SCOPE,)
    assert required_scopes_for("POST", "/agent-builder/assembly-plan") == (AGENT_BUILDER_CREATE_SCOPE,)
    assert required_scopes_for("POST", "/agent-builder/birth") == (AGENT_BUILDER_CREATE_SCOPE,)
    assert required_scopes_for("POST", "/agent-builder/simulate-upgrades") == (AGENT_BUILDER_SIMULATE_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle(
        "POST",
        "/agent-builder/birth",
        {"x-flow-memory-scopes": AGENT_BUILDER_READ_SCOPE},
        json.dumps({"name": "DeniedBuilder"}).encode(),
    )
    allowed = gateway.handle(
        "POST",
        "/agent-builder/birth",
        {"x-flow-memory-scopes": AGENT_BUILDER_CREATE_SCOPE},
        json.dumps({"name": "AllowedBuilder"}).encode(),
    )
    assert denied.status == 403
    assert allowed.status == 200


def test_cli_agent_builder_commands_return_json(tmp_path):
    env = _cli_env()
    defaults = subprocess.run(
        [sys.executable, "-m", "flow_memory", "agent-builder", "defaults", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    plan = subprocess.run(
        [sys.executable, "-m", "flow_memory", "agent-builder", "plan", "--name", "CliMira", "--archetype", "research-builder", "--purpose", "Help me build Flow Memory", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    birth = subprocess.run(
        [sys.executable, "-m", "flow_memory", "agent-builder", "birth", "--name", "CliMira", "--archetype", "research-builder", "--purpose", "Help me build Flow Memory", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    birth_payload = json.loads(birth.stdout)
    upgrades = subprocess.run(
        [sys.executable, "-m", "flow_memory", "agent-builder", "simulate-upgrades", "--agent", birth_payload["agent_id"], "--byok", "--wallet", "--onchain-dry-run", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert json.loads(defaults.stdout)["simple_mode_default"] is True
    assert json.loads(plan.stdout)["plan"]["first_agent_mode"] is True
    assert birth_payload["first_agent_requires_wallet"] is False
    assert json.loads(upgrades.stdout)["no_broadcast"] is True


def test_mission_control_agent_builder_fixture_is_valid():
    with open("dashboard/src/mock-data/agent-builder.json", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["ok"] is True
    assert payload["summary"]["route"] == "/agents/new"
    assert payload["summary"]["first_agent_requires_wallet"] is False
    assert payload["summary"]["first_agent_requires_api_key"] is False
    assert payload["summary"]["first_agent_requires_funds"] is False
    assert payload["summary"]["private_default"] is True
    assert payload["summary"]["network_learning_opt_in"] is True
    assert len(payload["capability_composer"]) >= 10
    assert payload["optional_upgrades"]["onchain"]["relay_status"] == "disabled"
    assert payload["invariants"]["transaction_broadcast"] is False


def test_agent_builder_release_evidence_and_decision():
    evidence = agent_builder_evidence(".")
    decision = verify_agent_builder_evidence(evidence)
    readiness = decide_release_readiness(".", target="public-alpha-agent-builder")

    assert evidence["ok"] is True
    assert evidence["agent_builder_browser_route_available"] is True
    assert evidence["no_first_agent_wallet_api_key_requirement"] is True
    assert evidence["no_private_key_invariant"] is True
    assert evidence["no_seed_phrase_invariant"] is True
    assert evidence["no_funds_moved_invariant"] is True
    assert evidence["no_broadcast_invariant"] is True
    assert decision["ok"] is True
    assert readiness.target == "public-alpha-agent-builder"
    assert "agent_builder" in readiness.required_evidence


def test_agent_builder_docs_contain_mermaid_and_safe_first_agent_language():
    docs = "\n".join(
        open(path, encoding="utf-8").read().lower()
        for path in (
            "docs/AGENT_BUILDER.md",
            "docs/START_HERE.md",
            "docs/AGENT_GENESIS.md",
            "docs/AGENT_INTERNET.md",
            "docs/BYOK_MODEL_KEYS.md",
            "docs/ONCHAIN_AGENT_UPGRADES.md",
            "docs/MISSION_CONTROL_QUICKSTART.md",
            "docs/PUBLIC_ALPHA_READINESS.md",
            "README.md",
        )
    )

    assert "```mermaid" in docs
    assert "agent builder architecture" in docs
    assert "first agent requires no wallet/api key/funds" in docs
    assert "byok is optional" in docs
    assert "wallet identity is optional" in docs
    assert "on-chain upgrade is dry-run only" in docs
    assert "network learning is opt-in" in docs
    assert "private memory is default" in docs
    for forbidden in (
        "private key stored",
        "seed phrase stored",
        "transaction broadcast enabled",
        "mainnet writes enabled",
        "funds required for first agent",
        "wallet required for first agent",
        "api key required for first agent",
        "unbounded autonomy enabled",
        "is conscious",
    ):
        assert forbidden not in docs
