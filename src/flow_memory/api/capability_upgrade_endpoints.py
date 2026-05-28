"""Local API endpoint handlers for optional capability upgrades."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.capability_upgrades import (
    activate_emergency_stop,
    approve_onchain_upgrade,
    bind_wallet_identity,
    create_credential_binding,
    emergency_stop_status,
    get_credential_binding,
    get_wallet_binding,
    list_credential_bindings,
    list_wallet_bindings,
    prepare_onchain_upgrade,
    prepare_x402_payment_route,
    provider_registry,
    relay_onchain_upgrade,
    request_external_signature,
    revoke_credential_binding,
    simulate_byok_inference_intent,
    simulate_onchain_upgrade,
    x402_adapter_status,
)

ROOT = Path(__file__).resolve().parents[3]


def byok_providers() -> Mapping[str, Any]:
    providers = provider_registry()
    return {"ok": True, "providers": providers, "count": len(providers)}


def byok_credentials_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return create_credential_binding(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("provider_id", payload.get("provider", ""))),
        str(payload.get("secret_ref", "")),
        user_id=str(payload.get("user_id", "local-user")),
        credential_kind=str(payload.get("credential_kind", "api_key")),
        scopes=tuple(payload.get("scopes", ()) or ()),
        budget_cap=float(payload.get("budget_cap", 0.0) or 0.0),
        root=ROOT,
    )


def byok_credentials(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", "")))
    records = list_credential_bindings(agent_id, root=ROOT)
    return {"ok": True, "credentials": records, "count": len(records)}


def byok_credential(credential_id: str) -> Mapping[str, Any]:
    return {"ok": True, "credential": get_credential_binding(credential_id, root=ROOT)}


def byok_credential_revoke(credential_id: str) -> Mapping[str, Any]:
    return revoke_credential_binding(credential_id, root=ROOT)


def byok_intent_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return simulate_byok_inference_intent(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("provider_id", payload.get("provider", ""))),
        str(payload.get("model_ref", payload.get("model", ""))),
        str(payload.get("purpose", "")),
        credential_id=str(payload.get("credential_id", "")),
        prompt_summary=str(payload.get("prompt_summary", "")),
        estimated_tokens=int(payload.get("estimated_tokens", 0) or 0),
        root=ROOT,
    )


def wallet_bindings_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return bind_wallet_identity(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("network", "base_sepolia")),
        str(payload.get("address", payload.get("wallet_address", ""))),
        user_id=str(payload.get("user_id", "local-user")),
        root=ROOT,
    )


def wallet_bindings(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", "")))
    records = list_wallet_bindings(agent_id, root=ROOT)
    return {"ok": True, "wallet_bindings": records, "count": len(records)}


def wallet_binding(wallet_binding_id: str) -> Mapping[str, Any]:
    return {"ok": True, "wallet_binding": get_wallet_binding(wallet_binding_id, root=ROOT)}


def onchain_upgrade_prepare(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return prepare_onchain_upgrade(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("network", "base_sepolia")),
        str(payload.get("action", "register_agent")),
        user_id=str(payload.get("user_id", "local-user")),
        root=ROOT,
    )


def onchain_upgrade_simulate(intent_id: str) -> Mapping[str, Any]:
    return simulate_onchain_upgrade(intent_id, root=ROOT)


def onchain_upgrade_approve(intent_id: str) -> Mapping[str, Any]:
    return approve_onchain_upgrade(intent_id, root=ROOT)


def onchain_upgrade_sign_request(intent_id: str) -> Mapping[str, Any]:
    return request_external_signature(intent_id, root=ROOT)


def onchain_upgrade_relay(intent_id: str) -> Mapping[str, Any]:
    return relay_onchain_upgrade(intent_id, root=ROOT)


def emergency_stop_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return activate_emergency_stop(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("scope", "all_upgrades")),
        str(payload.get("reason", "user requested")),
        user_id=str(payload.get("user_id", "local-user")),
        root=ROOT,
    )


def emergency_stop_agent(agent_id: str) -> Mapping[str, Any]:
    return emergency_stop_status(agent_id, root=ROOT)

def x402_status() -> Mapping[str, Any]:
    return x402_adapter_status()


def x402_route_prepare(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return prepare_x402_payment_route(
        str(payload.get("agent_id", payload.get("agent", ""))),
        str(payload.get("resource", "")),
        str(payload.get("price", "$0.001")),
        str(payload.get("pay_to", payload.get("payTo", ""))),
        facilitator=str(payload.get("facilitator", "x402_org_testnet")),
        network=str(payload.get("network", "eip155:84532")),
        live_requested=bool(payload.get("testnet_live", payload.get("live_requested", False))),
        root=ROOT,
    )
