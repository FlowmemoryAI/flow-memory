import json
import os
import subprocess
import sys
from pathlib import Path

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import (
    BYOK_READ_SCOPE,
    BYOK_WRITE_SCOPE,
    ONCHAIN_PREPARE_SCOPE,
    ONCHAIN_RELAY_SCOPE,
    WALLET_READ_SCOPE,
    WALLET_WRITE_SCOPE,
    X402_PREPARE_SCOPE,
    X402_READ_SCOPE,
    required_scopes_for,
)
from flow_memory.capability_upgrades import (
    bind_wallet_identity,
    create_credential_binding,
    emergency_stop_status,
    fingerprint_secret,
    prepare_onchain_upgrade,
    prepare_x402_payment_route,
    provider_registry,
    redact_secret,
    relay_onchain_upgrade,
    request_external_signature,
    revoke_credential_binding,
    simulate_byok_inference_intent,
    simulate_onchain_upgrade,
    validate_no_raw_secret_leak,
    x402_adapter_status,
)
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.release.byok_onchain_evidence import byok_onchain_upgrade_evidence, verify_byok_onchain_upgrade_evidence
from flow_memory.release.readiness import decide_release_readiness


REPO_SRC = Path(__file__).resolve().parents[1] / "src"


FLOWLANG_CAPABILITIES = '''
agent Mira {
  genesis {
    archetype: "research-builder"
    consent_mode: "private_only"
  }

  network {
    publish_identity: true
    payment_rail: "dry_run_x402"
  }

  capabilities {
    byok_enabled: false
    allowed_providers: ["openai", "openrouter", "anthropic", "local_runtime"]
    require_user_supplied_key: true
    store_raw_key: false
    budget_cap_usd: 5.00
    revoke_supported: true
    wallet_enabled: false
    network: "base_sepolia"
    mainnet_writes_enabled: false
    require_external_signature: true
    no_private_keys: true
    onchain_upgrade_enabled: false
    mode: "dry_run"
    prepare_sign_relay_separation: true
    relay_enabled: false
    allowed_actions: ["register_agent", "publish_agent_genome_hash", "publish_skill_manifest_hash"]
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
'''


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_SRC) if not existing else str(REPO_SRC) + os.pathsep + existing
    return env


def test_provider_registry_and_credential_redaction(tmp_path):
    providers = {record["provider_id"]: record for record in provider_registry()}
    assert {"openai", "openrouter", "anthropic", "local_runtime", "nookplot_gateway_stub", "custom_https_stub"}.issubset(providers)

    raw_secret = "sk-test-flowmemory-secret"
    credential = create_credential_binding("agent-upgrade", "openai", raw_secret, budget_cap=5.0, root=tmp_path)
    artifact = Path(tmp_path) / "artifacts" / "capability_upgrades" / "credentials" / f"{credential['credential_id']}.json"
    artifact_text = artifact.read_text(encoding="utf-8")

    assert credential["raw_secret_persisted"] is False
    assert credential["secret_ref"].startswith("fingerprint:secret_fp_")
    assert credential["secret_fingerprint"] == fingerprint_secret(raw_secret)
    assert redact_secret(raw_secret).startswith("redacted#secret_fp_")
    assert validate_no_raw_secret_leak(credential, raw_secret) is True
    assert raw_secret not in artifact_text

    revoked = revoke_credential_binding(credential["credential_id"], root=tmp_path)
    assert revoked["status"] == "revoked"


def test_byok_inference_intent_is_simulated(tmp_path):
    credential = create_credential_binding("agent-upgrade", "openai", "env:OPENAI_API_KEY", root=tmp_path)
    intent = simulate_byok_inference_intent(
        "agent-upgrade",
        "openai",
        "gpt-4.1-mini",
        "research",
        credential_id=credential["credential_id"],
        estimated_tokens=1200,
        root=tmp_path,
    )

    assert intent["status"] == "simulated"
    assert intent["no_external_call_performed"] is True
    assert intent["raw_prompt_excluded"] is True


def test_wallet_prepare_sign_relay_separation_and_emergency_stop(tmp_path):
    wallet = bind_wallet_identity("agent-upgrade", "base_sepolia", "0x0000000000000000000000000000000000000000", root=tmp_path)
    prepared = prepare_onchain_upgrade("agent-upgrade", "base_sepolia", "register_agent", root=tmp_path)
    simulated = simulate_onchain_upgrade(prepared["intent_id"], root=tmp_path)
    sign_request = request_external_signature(prepared["intent_id"], root=tmp_path)
    relay = relay_onchain_upgrade(prepared["intent_id"], root=tmp_path)

    assert wallet["chain_id"] == 84532
    assert wallet["mainnet_writes_enabled"] is False
    assert prepared["eip712_typed_data"]["domain"]["chainId"] == 84532
    assert simulated["simulation_result"]["no_broadcast"] is True
    assert sign_request["no_private_key_required"] is True
    assert sign_request["seed_phrase_requested"] is False
    assert relay["blocked"] is True
    assert relay["no_broadcast"] is True
    assert relay["no_funds_moved"] is True

    from flow_memory.capability_upgrades import activate_emergency_stop

    stop = activate_emergency_stop("agent-upgrade", "all_upgrades", "test stop", root=tmp_path)
    assert stop["emergency_stop"]["active"] is True
    assert emergency_stop_status("agent-upgrade", root=tmp_path)["active"] is True


def test_x402_status_and_route_prepare_are_live_ready_without_default_settlement(tmp_path):
    status = x402_adapter_status()
    route = prepare_x402_payment_route(
        "agent-upgrade",
        "skill_match",
        "0.001",
        "0x0000000000000000000000000000000000000000",
        live_requested=True,
        root=tmp_path,
    )

    assert status["recommended_install"] == 'python -m pip install "x402[fastapi,httpx,evm]>=2.11.0"'
    assert status["coinbase_facilitator_url"] == "https://api.cdp.coinbase.com/platform/v2/x402"
    assert route["network"] == "eip155:84532"
    assert route["testnet_live_ready"] is True
    assert route["settlement_enabled"] is False
    assert route["no_funds_moved"] is True
    assert route["no_broadcast"] is True
    assert route["payment_requirements_preview"]["payTo"] == "0x0000000000000000000000000000000000000000"


def test_flowlang_capability_block_converts_to_profile_metadata():
    ir = parse_flowlang(FLOWLANG_CAPABILITIES)
    profile = agent_profile_from_ir(ir)

    assert ir.metadata["capability_upgrades"]["store_raw_key"] is False
    assert ir.metadata["capability_upgrades"]["relay_enabled"] is False
    assert profile.metadata["capability_upgrades"]["network"] == "base_sepolia"


def test_upgrade_api_routes_and_scopes_are_enforced():
    router = create_default_router()
    providers = router.dispatch("GET", "/byok/providers")
    x402_status_payload = router.dispatch("GET", "/x402/status")
    x402_route = router.dispatch(
        "POST",
        "/x402/routes/prepare",
        {
            "agent_id": "api-upgrade-agent",
            "resource": "skill_match",
            "price": "0.001",
            "pay_to": "0x0000000000000000000000000000000000000000",
            "testnet_live": True,
        },
    )

    assert providers["ok"] is True
    assert x402_status_payload["ok"] is True
    assert x402_route["testnet_live_ready"] is True
    assert required_scopes_for("GET", "/byok/providers") == (BYOK_READ_SCOPE,)
    assert required_scopes_for("POST", "/byok/credentials") == (BYOK_WRITE_SCOPE,)
    assert required_scopes_for("GET", "/wallet/bindings") == (WALLET_READ_SCOPE,)
    assert required_scopes_for("POST", "/wallet/bindings") == (WALLET_WRITE_SCOPE,)
    assert required_scopes_for("POST", "/onchain/upgrades/prepare") == (ONCHAIN_PREPARE_SCOPE,)
    assert required_scopes_for("POST", "/onchain/upgrades/demo/relay") == (ONCHAIN_RELAY_SCOPE,)
    assert required_scopes_for("GET", "/x402/status") == (X402_READ_SCOPE,)
    assert required_scopes_for("POST", "/x402/routes/prepare") == (X402_PREPARE_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle(
        "POST",
        "/x402/routes/prepare",
        {"x-flow-memory-scopes": X402_READ_SCOPE},
        json.dumps({"agent_id": "api-upgrade-agent", "resource": "skill", "pay_to": "0x0000000000000000000000000000000000000000"}).encode(),
    )
    allowed = gateway.handle(
        "POST",
        "/x402/routes/prepare",
        {"x-flow-memory-scopes": X402_PREPARE_SCOPE},
        json.dumps({"agent_id": "api-upgrade-agent", "resource": "skill", "pay_to": "0x0000000000000000000000000000000000000000"}).encode(),
    )
    assert denied.status == 403
    assert allowed.status == 200


def test_cli_upgrade_commands_return_json(tmp_path):
    env = _cli_env()
    byok = subprocess.run(
        [sys.executable, "-m", "flow_memory", "byok", "providers", "list", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    x402 = subprocess.run(
        [
            sys.executable,
            "-m",
            "flow_memory",
            "x402",
            "route",
            "prepare",
            "--agent",
            "cli-upgrade-agent",
            "--resource",
            "skill_match",
            "--price",
            "0.001",
            "--pay-to",
            "0x0000000000000000000000000000000000000000",
            "--testnet-live",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert json.loads(byok.stdout)["count"] >= 6
    x402_payload = json.loads(x402.stdout)
    assert x402_payload["testnet_live_ready"] is True
    assert x402_payload["settlement_enabled"] is False
    assert x402_payload["no_broadcast"] is True


def test_mission_control_upgrade_fixture_is_valid():
    with open("dashboard/src/mock-data/byok-onchain-upgrades.json", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["ok"] is True
    assert payload["summary"]["first_agent_path"] == "no wallet/API key/funds required for first agent"
    assert payload["byok"]["raw_api_key_persisted"] is False
    assert payload["wallet"]["seed_phrase_required"] is False
    assert payload["onchain_upgrade"]["relay_status"] == "disabled"
    assert payload["x402"]["testnet_live_ready"] is True
    assert payload["x402"]["settlement_enabled"] is False
    assert payload["invariants"]["transaction_broadcast"] is False


def test_byok_onchain_release_evidence_and_decision():
    evidence = byok_onchain_upgrade_evidence(".")
    decision = verify_byok_onchain_upgrade_evidence(evidence)
    readiness = decide_release_readiness(".", target="public-alpha-agent-upgrades")

    assert evidence["byok_provider_registry_available"] is True
    assert evidence["x402_testnet_route_prepare_available"] is True
    assert evidence["x402_testnet_live_ready_without_default_broadcast"] is True
    assert evidence["no_private_key_invariant"] is True
    assert evidence["no_seed_phrase_invariant"] is True
    assert evidence["no_funds_moved_invariant"] is True
    assert evidence["no_transaction_broadcast_invariant"] is True
    assert decision["ok"] is True
    assert readiness.target == "public-alpha-agent-upgrades"
    assert "byok_onchain_upgrade" in readiness.required_evidence


def test_docs_contain_mermaid_and_no_dangerous_upgrade_claims():
    docs = "\n".join(
        open(path, encoding="utf-8").read().lower()
        for path in (
            "docs/BYOK_MODEL_KEYS.md",
            "docs/ONCHAIN_AGENT_UPGRADES.md",
            "docs/WALLET_SAFETY.md",
            "docs/MCP_X402_ERC8004_ADAPTERS.md",
            "README.md",
        )
    )

    assert "```mermaid" in docs
    assert "first agent does not require wallet/api key/funds" in docs
    assert "x402[fastapi,httpx,evm]>=2.11.0" in docs
    for forbidden in (
        "private key stored",
        "seed phrase stored",
        "transaction broadcast enabled",
        "mainnet writes enabled",
        "funds moved on-chain",
        "wallet required for first agent",
        "api key required for first agent",
    ):
        assert forbidden not in docs
