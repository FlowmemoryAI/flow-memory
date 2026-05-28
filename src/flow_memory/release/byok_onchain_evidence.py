"""Release evidence for optional BYOK and on-chain dry-run upgrade path."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import (
    BYOK_READ_SCOPE,
    BYOK_WRITE_SCOPE,
    EMERGENCY_WRITE_SCOPE,
    ONCHAIN_APPROVE_SCOPE,
    ONCHAIN_PREPARE_SCOPE,
    ONCHAIN_RELAY_SCOPE,
    WALLET_READ_SCOPE,
    WALLET_WRITE_SCOPE,
    X402_PREPARE_SCOPE,
    X402_READ_SCOPE,
    required_scopes_for,
)
from flow_memory.capability_upgrades import (
    demo_capability_upgrade,
    fingerprint_secret,
    provider_registry,
    redact_secret,
    validate_no_raw_secret_leak,
)
from flow_memory.flowlang.parser import parse_flowlang

_OVERCLAIMS = (
    "is agi",
    "achieves agi",
    "artificial general intelligence",
    "is conscious",
    "has consciousness",
    "private key stored",
    "seed phrase stored",
    "transaction broadcast enabled",
    "mainnet writes enabled",
    "funds moved on-chain",
    "wallet required for first agent",
    "api key required for first agent",
)

_REQUIRED_ROUTES = {
    "GET /byok/providers",
    "POST /byok/credentials",
    "GET /byok/credentials",
    "GET /byok/credentials/{credential_id}",
    "POST /byok/credentials/{credential_id}/revoke",
    "POST /byok/intents/simulate",
    "POST /wallet/bindings",
    "GET /wallet/bindings",
    "GET /wallet/bindings/{wallet_binding_id}",
    "POST /onchain/upgrades/prepare",
    "POST /onchain/upgrades/{intent_id}/simulate",
    "POST /onchain/upgrades/{intent_id}/approve",
    "POST /onchain/upgrades/{intent_id}/sign-request",
    "POST /onchain/upgrades/{intent_id}/relay",
    "POST /emergency-stop",
    "GET /emergency-stop/{agent_id}",
    "GET /x402/status",
    "POST /x402/routes/prepare",
}

_FLOWLANG_CAPABILITIES = """
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
"""


def byok_onchain_upgrade_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    with TemporaryDirectory() as tmp:
        demo = demo_capability_upgrade(tmp)
        fake_secret = "sk-test-flowmemory-raw-secret"
        fp = fingerprint_secret(fake_secret)
        redacted = redact_secret(fake_secret)
        leak_free = validate_no_raw_secret_leak({"secret_fingerprint": fp, "redacted_display": redacted}, fake_secret)
    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    flow = parse_flowlang(_FLOWLANG_CAPABILITIES)
    capabilities = dict(flow.metadata.get("capability_upgrades", {}))
    docs_text = _docs_text(root_path)
    dashboard_fixture = root_path / "dashboard" / "src" / "mock-data" / "byok-onchain-upgrades.json"
    dashboard_server = root_path / "dashboard" / "scripts" / "dev-server.mjs"
    credential = dict(demo.get("credential", {}))
    byok_intent = dict(demo.get("byok_intent", {}))
    wallet = dict(demo.get("wallet", {}))
    prepared = dict(demo.get("prepared", {}))
    simulated = dict(demo.get("simulated", {}))
    sign_request = dict(demo.get("sign_request", {}))
    relay = dict(demo.get("relay", {}))
    emergency = dict(demo.get("emergency_stop", {}))
    projection = dict(demo.get("projection", {}))
    x402_route = dict(demo.get("x402_route", {}))
    evidence = {
        "byok_provider_registry_available": len(provider_registry()) >= 6,
        "credential_binding_available": bool(credential.get("credential_id")),
        "raw_api_key_not_persisted": credential.get("raw_secret_persisted") is False and validate_no_raw_secret_leak(credential, "sk-test-flowmemory-raw-secret"),
        "raw_api_key_redaction_validated": leak_free and redacted.startswith("redacted#secret_fp_"),
        "credential_fingerprint_available": str(credential.get("secret_fingerprint", "")).startswith("secret_fp_"),
        "credential_revoke_available": _file_contains(root_path / "src" / "flow_memory" / "capability_upgrades" / "core.py", "def revoke_credential_binding"),
        "byok_intent_simulation_available": byok_intent.get("no_external_call_performed") is True and byok_intent.get("status") == "simulated",
        "wallet_binding_available": wallet.get("no_private_key_required") is True and wallet.get("no_seed_phrase_required") is True,
        "base_sepolia_default_available": wallet.get("network_name") == "base_sepolia" and wallet.get("chain_id") == 84532,
        "base_mainnet_write_disabled": wallet.get("mainnet_writes_enabled") is False,
        "onchain_prepare_available": bool(prepared.get("eip712_typed_data")) and prepared.get("no_private_key_required") is True,
        "onchain_simulation_available": simulated.get("simulation_result", {}).get("no_broadcast") is True,
        "onchain_approval_required": bool(prepared.get("approval_record_id")) and prepared.get("policy_decision", {}).get("approval_required") is True,
        "onchain_sign_request_external_only": sign_request.get("no_private_key_required") is True and sign_request.get("seed_phrase_requested") is False,
        "onchain_relay_disabled_by_default": relay.get("blocked") is True and relay.get("relay_status") == "disabled",
        "no_private_key_invariant": wallet.get("no_private_key_required") is True and prepared.get("no_private_key_required") is True,
        "no_seed_phrase_invariant": wallet.get("no_seed_phrase_required") is True and sign_request.get("seed_phrase_requested") is False,
        "no_funds_moved_invariant": relay.get("no_funds_moved") is True and prepared.get("no_funds_moved") is True,
        "no_transaction_broadcast_invariant": relay.get("no_broadcast") is True and prepared.get("no_broadcast") is True,
        "emergency_stop_available": bool(emergency.get("emergency_stop", {}).get("active")) and "byok" in tuple(emergency.get("disabled_capabilities", ())),
        "dashboard_upgrade_panel_available": dashboard_fixture.exists() and _file_contains(dashboard_server, "BYOK Model Keys"),
        "x402_sdk_optional_dependency_available": _file_contains(root_path / "pyproject.toml", "x402>=2.11.0"),
        "x402_coinbase_facilitator_config_available": x402_route.get("x402_package_status", {}).get("coinbase_facilitator_url") == "https://api.cdp.coinbase.com/platform/v2/x402",
        "x402_testnet_route_prepare_available": x402_route.get("testnet_live_ready") is True and x402_route.get("settlement_enabled") is False,
        "x402_testnet_live_ready_without_default_broadcast": x402_route.get("no_broadcast") is True and x402_route.get("no_funds_moved") is True,
        "cli_byok_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "def _byok") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", '"byok"'),
        "cli_onchain_upgrade_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "def _onchain") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", '"onchain"'),
        "api_byok_available": _REQUIRED_ROUTES.issubset(manifest_routes) and _REQUIRED_ROUTES.issubset(registered_routes) and _scope_checks_ok(),
        "api_onchain_upgrade_available": _REQUIRED_ROUTES.issubset(manifest_routes) and _REQUIRED_ROUTES.issubset(registered_routes) and _scope_checks_ok(),
        "agent_internet_capability_projection_available": projection.get("projected") is True and projection.get("identity", {}).get("byok_capability_status") == "bound",
        "flowlang_capability_block_available": capabilities.get("store_raw_key") is False and capabilities.get("relay_enabled") is False,
        "x402_cli_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "def _x402") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", '"x402"'),
        "x402_api_available": _REQUIRED_ROUTES.issubset(manifest_routes) and _REQUIRED_ROUTES.issubset(registered_routes) and _scope_checks_ok(),
        "public_alpha_docs_updated": all((root_path / path).exists() for path in ("docs/BYOK_MODEL_KEYS.md", "docs/ONCHAIN_AGENT_UPGRADES.md", "docs/WALLET_SAFETY.md")) and "```mermaid" in docs_text,
        "first_agent_no_wallet_or_key_documented": "first agent does not require wallet/api key/funds" in docs_text,
        "no_overclaim_invariant": _no_overclaims(docs_text),
    }
    return {
        "ok": all(evidence.values()),
        **evidence,
        "demo": demo,
        "api_routes": tuple(sorted(_REQUIRED_ROUTES)),
        "flowlang_capability_upgrades": capabilities,
        "safety_authority": "PolicyEngine and ApprovalGate",
        "artifact_paths": {
            "credentials": "artifacts/capability_upgrades/credentials/",
            "wallet_bindings": "artifacts/capability_upgrades/wallet_bindings/",
            "onchain_intents": "artifacts/capability_upgrades/onchain_intents/",
            "emergency_stops": "artifacts/capability_upgrades/emergency_stops/",
            "x402_routes": "artifacts/capability_upgrades/x402_routes/",
        },
    }


def verify_byok_onchain_upgrade_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    required = (
        "byok_provider_registry_available",
        "credential_binding_available",
        "raw_api_key_not_persisted",
        "raw_api_key_redaction_validated",
        "credential_fingerprint_available",
        "credential_revoke_available",
        "byok_intent_simulation_available",
        "wallet_binding_available",
        "base_sepolia_default_available",
        "base_mainnet_write_disabled",
        "onchain_prepare_available",
        "onchain_simulation_available",
        "onchain_approval_required",
        "onchain_sign_request_external_only",
        "onchain_relay_disabled_by_default",
        "no_private_key_invariant",
        "no_seed_phrase_invariant",
        "no_funds_moved_invariant",
        "no_transaction_broadcast_invariant",
        "emergency_stop_available",
        "dashboard_upgrade_panel_available",
        "cli_byok_available",
        "cli_onchain_upgrade_available",
        "api_byok_available",
        "api_onchain_upgrade_available",
        "agent_internet_capability_projection_available",
        "flowlang_capability_block_available",
        "public_alpha_docs_updated",
        "first_agent_no_wallet_or_key_documented",
        "no_overclaim_invariant",
        "x402_sdk_optional_dependency_available",
        "x402_coinbase_facilitator_config_available",
        "x402_testnet_route_prepare_available",
        "x402_testnet_live_ready_without_default_broadcast",
        "x402_cli_available",
        "x402_api_available",
    )
    if record.get("ok") is not True:
        blockers.append("byok_onchain_evidence_not_ok")
    for key in required:
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    demo = record.get("demo", {}) if isinstance(record.get("demo", {}), Mapping) else {}
    relay = demo.get("relay", {}) if isinstance(demo.get("relay", {}), Mapping) else {}
    prepared = demo.get("prepared", {}) if isinstance(demo.get("prepared", {}), Mapping) else {}
    credential = demo.get("credential", {}) if isinstance(demo.get("credential", {}), Mapping) else {}
    if relay.get("no_broadcast") is not True:
        blockers.append("relay_broadcasts_transaction")
    if relay.get("no_funds_moved") is not True:
        blockers.append("relay_moves_funds")
    if prepared.get("mode") == "mainnet_disabled" and relay.get("blocked") is not True:
        blockers.append("mainnet_relay_not_blocked")
    if credential.get("raw_secret_persisted") is not False:
        blockers.append("raw_secret_persisted")
    return {"ok": not blockers, "blockers": tuple(blockers)}


def _scope_checks_ok() -> bool:
    return (
        required_scopes_for("GET", "/byok/providers") == (BYOK_READ_SCOPE,)
        and required_scopes_for("POST", "/byok/credentials") == (BYOK_WRITE_SCOPE,)
        and required_scopes_for("GET", "/wallet/bindings") == (WALLET_READ_SCOPE,)
        and required_scopes_for("POST", "/wallet/bindings") == (WALLET_WRITE_SCOPE,)
        and required_scopes_for("POST", "/onchain/upgrades/prepare") == (ONCHAIN_PREPARE_SCOPE,)
        and required_scopes_for("POST", "/onchain/upgrades/demo/approve") == (ONCHAIN_APPROVE_SCOPE,)
        and required_scopes_for("POST", "/onchain/upgrades/demo/relay") == (ONCHAIN_RELAY_SCOPE,)
        and required_scopes_for("POST", "/emergency-stop") == (EMERGENCY_WRITE_SCOPE,)
        and required_scopes_for("GET", "/x402/status") == (X402_READ_SCOPE,)
        and required_scopes_for("POST", "/x402/routes/prepare") == (X402_PREPARE_SCOPE,)
    )


def _docs_text(root: Path) -> str:
    chunks: list[str] = []
    for relative in (
        "README.md",
        "BUILD_REPORT.md",
        "FLOW_MEMORY_STATUS.md",
        "AGENTS.md",
        "docs/BYOK_MODEL_KEYS.md",
        "docs/ONCHAIN_AGENT_UPGRADES.md",
        "docs/WALLET_SAFETY.md",
        "docs/AGENT_GENESIS.md",
        "docs/AGENT_INTERNET.md",
        "docs/MCP_X402_ERC8004_ADAPTERS.md",
        "docs/PUBLIC_ALPHA_READINESS.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
    ):
        path = root / relative
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks).lower()


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8")


def _no_overclaims(text: str) -> bool:
    return not any(pattern in text for pattern in _OVERCLAIMS)
