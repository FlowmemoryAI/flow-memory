"""Optional BYOK, wallet identity, and on-chain dry-run capability upgrades.

The first Agent Genesis path stays local and policy-gated.  This module only
models post-birth capability upgrades and keeps every external effect simulated
unless a future reviewed implementation explicitly changes that behavior.
"""
from __future__ import annotations

import hashlib
import json
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_ROOT = Path("artifacts/capability_upgrades")
DEFAULT_USER_ID = "local-user"
NETWORKS: Mapping[str, Mapping[str, Any]] = {
    "base_sepolia": {
        "network_name": "base_sepolia",
        "chain_id": 84532,
        "mode": "dry_run",
        "mainnet_writes_enabled": False,
        "write_enabled": False,
    },
    "base_mainnet_readonly": {
        "network_name": "base_mainnet_readonly",
        "chain_id": 8453,
        "mode": "mainnet_disabled",
        "mainnet_writes_enabled": False,
        "write_enabled": False,
    },
}
ALLOWED_ONCHAIN_ACTIONS = (
    "register_agent",
    "bind_wallet_identity",
    "publish_agent_genome_hash",
    "publish_reputation_ref",
    "publish_skill_manifest_hash",
)
X402_FACILITATORS: Mapping[str, Mapping[str, Any]] = {
    "x402_org_testnet": {
        "facilitator_url": "https://x402.org/facilitator",
        "network": "eip155:84532",
        "requires_cdp_api_key": False,
        "mode": "testnet",
    },
    "coinbase_cdp": {
        "facilitator_url": "https://api.cdp.coinbase.com/platform/v2/x402",
        "network": "eip155:84532",
        "requires_cdp_api_key": True,
        "mode": "testnet_or_mainnet",
    },
}


@dataclass(frozen=True)
class CapabilityUpgradeRecord:
    upgrade_id: str
    agent_id: str
    user_id: str
    upgrade_type: str
    status: str = "proposed"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    policy_state: Mapping[str, Any] = field(default_factory=lambda: {"policy_gated": True, "approval_required": True})
    approval_state: Mapping[str, Any] = field(default_factory=lambda: {"status": "required"})
    risk_level: str = "medium"
    audit_refs: tuple[str, ...] = ()
    no_private_key_required: bool = True
    no_funds_moved: bool = True
    no_broadcast: bool = True
    mainnet_enabled: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "upgrade_id": self.upgrade_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "upgrade_type": self.upgrade_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "policy_state": dict(self.policy_state),
            "approval_state": dict(self.approval_state),
            "risk_level": self.risk_level,
            "audit_refs": self.audit_refs,
            "no_private_key_required": self.no_private_key_required,
            "no_funds_moved": self.no_funds_moved,
            "no_broadcast": self.no_broadcast,
            "mainnet_enabled": self.mainnet_enabled,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BYOKProvider:
    provider_id: str
    display_name: str
    provider_type: str
    supported_model_refs: tuple[str, ...]
    key_format_hint: str
    scopes_supported: tuple[str, ...]
    budget_caps_supported: bool = True
    test_mode_supported: bool = True
    status: str = "available"
    docs_url: str = ""
    risk_notes: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "provider_type": self.provider_type,
            "supported_model_refs": self.supported_model_refs,
            "key_format_hint": self.key_format_hint,
            "scopes_supported": self.scopes_supported,
            "budget_caps_supported": self.budget_caps_supported,
            "test_mode_supported": self.test_mode_supported,
            "status": self.status,
            "docs_url": self.docs_url,
            "risk_notes": self.risk_notes,
            "external_calls_default": False,
        }


@dataclass(frozen=True)
class CredentialBinding:
    credential_id: str
    agent_id: str
    user_id: str
    provider_id: str
    credential_kind: str = "api_key"
    secret_ref: str = ""
    secret_fingerprint: str = ""
    encrypted_secret_ref: str = ""
    redacted_display: str = ""
    scopes: tuple[str, ...] = ()
    budget_cap: float = 0.0
    rate_limit: str = "local_public_alpha"
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    revoked_at: str = ""
    audit_refs: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "provider_id": self.provider_id,
            "credential_kind": self.credential_kind,
            "secret_ref": self.secret_ref,
            "secret_fingerprint": self.secret_fingerprint,
            "encrypted_secret_ref": self.encrypted_secret_ref,
            "redacted_display": self.redacted_display,
            "scopes": self.scopes,
            "budget_cap": round(float(self.budget_cap), 4),
            "rate_limit": self.rate_limit,
            "status": self.status,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "audit_refs": self.audit_refs,
            "raw_secret_persisted": False,
        }


@dataclass(frozen=True)
class BYOKInferenceIntent:
    intent_id: str
    agent_id: str
    provider_id: str
    credential_id: str
    model_ref: str
    purpose: str
    prompt_summary: str = ""
    raw_prompt_excluded: bool = True
    estimated_tokens: int = 0
    budget_check: Mapping[str, Any] = field(default_factory=lambda: {"ok": True, "mode": "simulated"})
    policy_decision: Mapping[str, Any] = field(default_factory=lambda: {"allowed": True, "mode": "simulated", "approval_required": True})
    status: str = "simulated"
    no_external_call_performed: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "provider_id": self.provider_id,
            "credential_id": self.credential_id,
            "model_ref": self.model_ref,
            "purpose": self.purpose,
            "prompt_summary": self.prompt_summary,
            "raw_prompt_excluded": self.raw_prompt_excluded,
            "estimated_tokens": int(self.estimated_tokens),
            "budget_check": dict(self.budget_check),
            "policy_decision": dict(self.policy_decision),
            "status": self.status,
            "no_external_call_performed": self.no_external_call_performed,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class WalletIdentityBinding:
    wallet_binding_id: str
    agent_id: str
    user_id: str
    chain_id: int
    network_name: str
    wallet_address: str
    proof_type: str = "address_only_stub"
    verification_status: str = "simulated"
    allowed_capabilities: tuple[str, ...] = ("dry_run_identity", "external_signature_future")
    spend_limits: Mapping[str, Any] = field(default_factory=lambda: {"native": 0, "token": 0})
    gas_limits: Mapping[str, Any] = field(default_factory=lambda: {"max_gas": 0, "dry_run_only": True})
    token_allowlist: tuple[str, ...] = ()
    method_allowlist: tuple[str, ...] = ALLOWED_ONCHAIN_ACTIONS
    revoked: bool = False
    emergency_stopped: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "wallet_binding_id": self.wallet_binding_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "chain_id": self.chain_id,
            "network_name": self.network_name,
            "wallet_address": self.wallet_address,
            "proof_type": self.proof_type,
            "verification_status": self.verification_status,
            "allowed_capabilities": self.allowed_capabilities,
            "spend_limits": dict(self.spend_limits),
            "gas_limits": dict(self.gas_limits),
            "token_allowlist": self.token_allowlist,
            "method_allowlist": self.method_allowlist,
            "revoked": self.revoked,
            "emergency_stopped": self.emergency_stopped,
            "no_private_key_required": True,
            "no_seed_phrase_required": True,
            "no_broadcast": True,
            "no_funds_moved": True,
            "mainnet_writes_enabled": False,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class OnchainAgentUpgradeIntent:
    intent_id: str
    agent_id: str
    user_id: str
    network: str
    chain_id: int
    action: str
    mode: str = "dry_run"
    prepared_payload: Mapping[str, Any] = field(default_factory=dict)
    eip712_typed_data: Mapping[str, Any] = field(default_factory=dict)
    simulation_result: Mapping[str, Any] = field(default_factory=dict)
    policy_decision: Mapping[str, Any] = field(default_factory=lambda: {"allowed": False, "reason": "simulation_required"})
    approval_record_id: str = ""
    sign_status: str = "not_requested"
    relay_status: str = "disabled"
    no_private_key_required: bool = True
    no_funds_moved: bool = True
    no_broadcast: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "network": self.network,
            "chain_id": self.chain_id,
            "mode": self.mode,
            "action": self.action,
            "prepared_payload": dict(self.prepared_payload),
            "eip712_typed_data": dict(self.eip712_typed_data),
            "simulation_result": dict(self.simulation_result),
            "policy_decision": dict(self.policy_decision),
            "approval_record_id": self.approval_record_id,
            "sign_status": self.sign_status,
            "relay_status": self.relay_status,
            "no_private_key_required": self.no_private_key_required,
            "no_funds_moved": self.no_funds_moved,
            "no_broadcast": self.no_broadcast,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    agent_id: str
    user_id: str
    action_type: str
    target_ref: str
    risk_level: str = "medium"
    status: str = "required"
    approval_reason: str = "human approval required for optional capability upgrade"
    created_at: str = field(default_factory=utc_now)
    decided_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "target_ref": self.target_ref,
            "risk_level": self.risk_level,
            "status": self.status,
            "approval_reason": self.approval_reason,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True)
class EmergencyStopRecord:
    stop_id: str
    agent_id: str
    user_id: str
    scope: str
    reason: str
    active: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "stop_id": self.stop_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "scope": self.scope,
            "reason": self.reason,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class X402PaymentRoute:
    route_id: str
    agent_id: str
    resource: str
    price: str
    pay_to: str
    network: str = "eip155:84532"
    facilitator_url: str = "https://x402.org/facilitator"
    facilitator_provider: str = "x402_org_testnet"
    mode: str = "testnet_live_ready"
    status: str = "prepared"
    settlement_enabled: bool = False
    no_private_key_required: bool = True
    no_seed_phrase_required: bool = True
    no_funds_moved: bool = True
    no_broadcast: bool = True
    cdp_api_key_required: bool = False
    package_required: str = "x402[fastapi,httpx,evm]>=2.11.0"
    created_at: str = field(default_factory=utc_now)
    testnet_live_ready: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "agent_id": self.agent_id,
            "resource": self.resource,
            "price": self.price,
            "pay_to": self.pay_to,
            "network": self.network,
            "facilitator_url": self.facilitator_url,
            "facilitator_provider": self.facilitator_provider,
            "mode": self.mode,
            "status": self.status,
            "settlement_enabled": self.settlement_enabled,
            "testnet_live_ready": self.testnet_live_ready,
            "no_private_key_required": self.no_private_key_required,
            "no_seed_phrase_required": self.no_seed_phrase_required,
            "no_funds_moved": self.no_funds_moved,
            "no_broadcast": self.no_broadcast,
            "cdp_api_key_required": self.cdp_api_key_required,
            "package_required": self.package_required,
            "install_command": "python -m pip install \"x402[fastapi,httpx,evm]>=2.11.0\"",
            "created_at": self.created_at,
        }

def provider_registry() -> tuple[Mapping[str, Any], ...]:
    return tuple(provider.as_record() for provider in (
        BYOKProvider("openai", "OpenAI", "model_provider", ("gpt-4.1-mini", "gpt-4.1"), "env:OPENAI_API_KEY or secret reference", ("inference", "embeddings"), docs_url="https://platform.openai.com/docs", risk_notes=("external calls disabled by default",)),
        BYOKProvider("openrouter", "OpenRouter", "model_provider", ("openrouter/auto",), "env:OPENROUTER_API_KEY or secret reference", ("inference",), status="available", risk_notes=("external calls disabled by default",)),
        BYOKProvider("anthropic", "Anthropic", "model_provider", ("claude-3-5-sonnet",), "env:ANTHROPIC_API_KEY or secret reference", ("inference",), status="available", risk_notes=("external calls disabled by default",)),
        BYOKProvider("local_runtime", "Local Runtime", "local", ("tiny_torch", "none"), "no key required", ("local_inference",), budget_caps_supported=False, status="available"),
        BYOKProvider("nookplot_gateway_stub", "Nookplot Gateway Stub", "gateway_stub", ("gateway-simulated",), "session or gateway secret reference", ("inference_proxy",), status="stub", risk_notes=("inspiration seam only", "no external calls")),
        BYOKProvider("custom_https_stub", "Custom HTTPS Stub", "custom_stub", ("custom-model-ref",), "secret://provider/ref", ("inference_proxy",), status="stub", risk_notes=("manifest and policy review required",)),
    ))


def get_provider(provider_id: str) -> Mapping[str, Any]:
    for provider in provider_registry():
        if provider.get("provider_id") == provider_id:
            return provider
    raise KeyError(f"unknown BYOK provider: {provider_id}")


def create_capability_upgrade(agent_id: str, user_id: str, upgrade_type: str, *, status: str = "proposed", risk_level: str = "medium", metadata: Mapping[str, Any] | None = None, root: str | Path = ".") -> Mapping[str, Any]:
    upgrade = CapabilityUpgradeRecord(
        upgrade_id=stable_id("capability_upgrade", agent_id, user_id, upgrade_type, status),
        agent_id=agent_id,
        user_id=user_id,
        upgrade_type=upgrade_type,
        status=status,
        risk_level=risk_level,
        metadata=dict(metadata or {}),
    )
    return _write_record(root, "upgrades", upgrade.upgrade_id, upgrade.as_record())


def list_capability_upgrades(agent_id: str = "", *, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    records = _list_records(root, "upgrades")
    return tuple(record for record in records if not agent_id or record.get("agent_id") == agent_id)


def fingerprint_secret(secret: str) -> str:
    value = str(secret or "")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"secret_fp_{digest[:16]}"


def redact_secret(secret: str) -> str:
    value = str(secret or "")
    fp = fingerprint_secret(value)
    if value.startswith("env:"):
        return f"env:{value.split(':', 1)[1]}#{fp}"
    if value.startswith(("secret:", "secret://", "keyring:", "os-keyring:")):
        return f"secret-ref#{fp}"
    if not value:
        return f"empty#{fp}"
    return f"redacted#{fp}"


def validate_no_raw_secret_leak(payload: Mapping[str, Any] | Sequence[Any] | str, raw_secret: str) -> bool:
    secret = str(raw_secret or "")
    if not secret:
        return True
    text = json.dumps(payload, sort_keys=True, default=str) if not isinstance(payload, str) else payload
    return secret not in text


def create_credential_binding(agent_id: str, provider_id: str, secret_ref: str, *, user_id: str = DEFAULT_USER_ID, credential_kind: str = "api_key", scopes: Sequence[str] = (), budget_cap: float = 0.0, rate_limit: str = "local_public_alpha", status: str = "active", root: str | Path = ".") -> Mapping[str, Any]:
    get_provider(provider_id)
    fp = fingerprint_secret(secret_ref)
    stored_ref = _stored_secret_ref(secret_ref, fp)
    credential = CredentialBinding(
        credential_id=stable_id("credential_binding", agent_id, provider_id, fp),
        agent_id=agent_id,
        user_id=user_id,
        provider_id=provider_id,
        credential_kind=credential_kind,
        secret_ref=stored_ref,
        secret_fingerprint=fp,
        encrypted_secret_ref=f"metadata_only:{fp}",
        redacted_display=redact_secret(secret_ref),
        scopes=tuple(_clean_tuple(scopes or get_provider(provider_id).get("scopes_supported", ()))) if provider_id != "local_runtime" else ("local_inference",),
        budget_cap=float(budget_cap or 0.0),
        rate_limit=rate_limit,
        status=status,
        audit_refs=("raw_secret_excluded", "metadata_only_secret_ref"),
    )
    payload = credential.as_record()
    if not validate_no_raw_secret_leak(payload, secret_ref) and not secret_ref.startswith(("env:", "secret:", "secret://", "keyring:", "os-keyring:")):
        raise ValueError("raw secret leaked into credential metadata")
    create_capability_upgrade(agent_id, user_id, "model_provider_key", status="active", risk_level="medium", metadata={"provider_id": provider_id, "credential_id": credential.credential_id}, root=root)
    return _write_record(root, "credentials", credential.credential_id, payload)


def revoke_credential_binding(credential_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_credential_binding(credential_id, root=root))
    record["status"] = "revoked"
    record["revoked_at"] = utc_now()
    return _write_record(root, "credentials", credential_id, record)


def get_credential_binding(credential_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "credentials", credential_id)


def list_credential_bindings(agent_id: str = "", *, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    records = _list_records(root, "credentials")
    return tuple(record for record in records if not agent_id or record.get("agent_id") == agent_id)


def simulate_byok_inference_intent(agent_id: str, provider_id: str, model_ref: str, purpose: str, *, credential_id: str = "", prompt_summary: str = "", estimated_tokens: int = 0, root: str | Path = ".") -> Mapping[str, Any]:
    provider = get_provider(provider_id)
    credentials = list_credential_bindings(agent_id, root=root)
    credential = dict(get_credential_binding(credential_id, root=root)) if credential_id else next((dict(item) for item in credentials if item.get("provider_id") == provider_id and item.get("status") == "active"), {})
    stopped = emergency_stop_status(agent_id, root=root)
    blocked = bool(stopped.get("active")) or (provider_id != "local_runtime" and not credential)
    decision = {
        "allowed": not blocked,
        "mode": "simulated",
        "approval_required": True,
        "reason": "emergency_stop_active" if stopped.get("active") else ("credential_required" if provider_id != "local_runtime" and not credential else "simulation_only"),
    }
    intent = BYOKInferenceIntent(
        intent_id=stable_id("byok_intent", agent_id, provider_id, model_ref, purpose, credential.get("credential_id", credential_id)),
        agent_id=agent_id,
        provider_id=provider_id,
        credential_id=str(credential.get("credential_id", credential_id)),
        model_ref=model_ref or str(tuple(provider.get("supported_model_refs", ("model",)))[0]),
        purpose=purpose,
        prompt_summary=prompt_summary,
        estimated_tokens=int(estimated_tokens or 0),
        budget_check={"ok": not blocked, "mode": "simulated", "budget_caps_supported": bool(provider.get("budget_caps_supported"))},
        policy_decision=decision,
        status="blocked" if blocked else "simulated",
    )
    create_capability_upgrade(agent_id, DEFAULT_USER_ID, "model_provider_key", status="simulated" if not blocked else "denied", metadata={"provider_id": provider_id, "intent_id": intent.intent_id}, root=root)
    return _write_record(root, "byok_intents", intent.intent_id, intent.as_record())


def bind_wallet_identity(agent_id: str, network: str, wallet_address: str, *, user_id: str = DEFAULT_USER_ID, root: str | Path = ".") -> Mapping[str, Any]:
    config = _network_config(network)
    if not _looks_like_address(wallet_address):
        raise ValueError("wallet address must be a 0x-prefixed 20-byte address")
    stopped = emergency_stop_status(agent_id, root=root)
    binding = WalletIdentityBinding(
        wallet_binding_id=stable_id("wallet_binding", agent_id, config["network_name"], wallet_address.lower()),
        agent_id=agent_id,
        user_id=user_id,
        chain_id=int(config["chain_id"]),
        network_name=str(config["network_name"]),
        wallet_address=wallet_address.lower(),
        emergency_stopped=bool(stopped.get("active")),
        verification_status="simulated" if not stopped.get("active") else "unverified",
    )
    create_capability_upgrade(agent_id, user_id, "wallet_identity", status="simulated" if not stopped.get("active") else "emergency_stopped", metadata={"wallet_binding_id": binding.wallet_binding_id}, root=root)
    return _write_record(root, "wallet_bindings", binding.wallet_binding_id, binding.as_record())


def list_wallet_bindings(agent_id: str = "", *, root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    records = _list_records(root, "wallet_bindings")
    return tuple(record for record in records if not agent_id or record.get("agent_id") == agent_id)


def get_wallet_binding(wallet_binding_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "wallet_bindings", wallet_binding_id)


def wallet_status(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    bindings = list_wallet_bindings(agent_id, root=root)
    return {
        "ok": True,
        "agent_id": agent_id,
        "bindings": bindings,
        "wallet_binding_status": "bound" if bindings else "not_bound",
        "base_sepolia_default_available": True,
        "base_mainnet_write_disabled": True,
        "no_private_key_required": True,
        "no_seed_phrase_required": True,
    }


def prepare_onchain_upgrade(agent_id: str, network: str, action: str, *, user_id: str = DEFAULT_USER_ID, root: str | Path = ".") -> Mapping[str, Any]:
    config = _network_config(network)
    if action not in ALLOWED_ONCHAIN_ACTIONS:
        raise ValueError(f"unsupported on-chain dry-run action: {action}")
    mode = "mainnet_disabled" if config["network_name"] == "base_mainnet_readonly" else "dry_run"
    intent_id = stable_id("onchain_upgrade", agent_id, user_id, config["network_name"], action)
    approval = ApprovalRecord(
        approval_id=stable_id("approval", agent_id, intent_id, action),
        agent_id=agent_id,
        user_id=user_id,
        action_type=f"onchain:{action}",
        target_ref=intent_id,
        risk_level="high" if config["network_name"] == "base_mainnet_readonly" else "medium",
        status="required",
    )
    prepared = {
        "intent_id": intent_id,
        "agent_id": agent_id,
        "action": action,
        "network": config["network_name"],
        "chain_id": config["chain_id"],
        "dry_run_only": True,
        "method_allowlist": ALLOWED_ONCHAIN_ACTIONS,
        "spend_limit": 0,
    }
    typed_data = {
        "domain": {"name": "FlowMemoryAgentUpgrade", "version": "0", "chainId": config["chain_id"]},
        "primaryType": "AgentUpgradeIntent",
        "message": {"agentId": agent_id, "action": action, "intentId": intent_id, "dryRunOnly": True},
        "types": {"AgentUpgradeIntent": ("agentId", "action", "intentId", "dryRunOnly")},
    }
    intent = OnchainAgentUpgradeIntent(
        intent_id=intent_id,
        agent_id=agent_id,
        user_id=user_id,
        network=str(config["network_name"]),
        chain_id=int(config["chain_id"]),
        action=action,
        mode=mode,
        prepared_payload=prepared,
        eip712_typed_data=typed_data,
        policy_decision={"allowed": False, "approval_required": True, "reason": "simulate_then_external_sign"},
        approval_record_id=approval.approval_id,
    )
    _write_record(root, "approvals", approval.approval_id, approval.as_record())
    create_capability_upgrade(agent_id, user_id, "onchain_dry_run", status="approval_required", risk_level=approval.risk_level, metadata={"intent_id": intent.intent_id}, root=root)
    return _write_record(root, "onchain_intents", intent.intent_id, intent.as_record())


def get_onchain_upgrade_intent(intent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    return _read_record(root, "onchain_intents", intent_id)


def simulate_onchain_upgrade(intent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_onchain_upgrade_intent(intent_id, root=root))
    stopped = emergency_stop_status(str(record.get("agent_id", "")), root=root)
    mainnet = record.get("mode") == "mainnet_disabled" or record.get("network") == "base_mainnet_readonly"
    allowed = not stopped.get("active") and not mainnet
    record["simulation_result"] = {
        "ok": allowed,
        "mode": record.get("mode"),
        "gas_estimate": 0,
        "spend_limit": 0,
        "method_allowed": record.get("action") in ALLOWED_ONCHAIN_ACTIONS,
        "mainnet_write_blocked": bool(mainnet),
        "emergency_stop_active": bool(stopped.get("active")),
        "no_funds_moved": True,
        "no_broadcast": True,
    }
    record["policy_decision"] = {"allowed": allowed, "approval_required": True, "reason": "dry_run_simulation" if allowed else "mainnet_or_emergency_stop_block"}
    return _write_record(root, "onchain_intents", intent_id, record)


def approve_onchain_upgrade(intent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_onchain_upgrade_intent(intent_id, root=root))
    approval_id = str(record.get("approval_record_id", ""))
    approval = dict(_read_record(root, "approvals", approval_id)) if approval_id else {}
    approval.update({"status": "approved", "decided_at": utc_now(), "approval_reason": "human-approved dry-run preparation"})
    if approval_id:
        _write_record(root, "approvals", approval_id, approval)
    record["policy_decision"] = {**dict(record.get("policy_decision", {})), "human_approval_recorded": True, "approval_id": approval_id}
    return {"ok": True, "approval": approval, "intent": _write_record(root, "onchain_intents", intent_id, record)}


def request_external_signature(intent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_onchain_upgrade_intent(intent_id, root=root))
    record["sign_status"] = "external_signature_required"
    record["signature_request"] = {
        "instructions": "Review typed data in an external wallet. Flow Memory does not sign or hold private keys.",
        "typed_data": dict(record.get("eip712_typed_data", {})),
        "no_private_key_required": True,
        "seed_phrase_requested": False,
    }
    written = _write_record(root, "onchain_intents", intent_id, record)
    return {"ok": True, "intent_id": intent_id, "sign_status": "external_signature_required", "typed_data": record["signature_request"]["typed_data"], "no_private_key_required": True, "seed_phrase_requested": False, "intent": written}


def relay_onchain_upgrade(intent_id: str, *, enable_testnet_relay: bool = False, root: str | Path = ".") -> Mapping[str, Any]:
    record = dict(get_onchain_upgrade_intent(intent_id, root=root))
    mainnet = record.get("mode") == "mainnet_disabled" or record.get("network") == "base_mainnet_readonly"
    blocked = True
    reason = "relay_disabled_by_default"
    if mainnet:
        reason = "mainnet_relay_blocked"
    elif enable_testnet_relay:
        reason = "future_testnet_relay_not_implemented"
    record["relay_status"] = "disabled"
    record["no_broadcast"] = True
    written = _write_record(root, "onchain_intents", intent_id, record)
    return {"ok": True, "blocked": blocked, "reason": reason, "relay_status": "disabled", "no_broadcast": True, "no_funds_moved": True, "intent": written}


def activate_emergency_stop(agent_id: str, scope: str, reason: str, *, user_id: str = DEFAULT_USER_ID, root: str | Path = ".") -> Mapping[str, Any]:
    stop = EmergencyStopRecord(
        stop_id=stable_id("emergency_stop", agent_id, user_id, scope, reason),
        agent_id=agent_id,
        user_id=user_id,
        scope=scope,
        reason=reason,
        active=True,
    )
    record = _write_record(root, "emergency_stops", stop.stop_id, stop.as_record())
    create_capability_upgrade(agent_id, user_id, scope if scope in {"byok", "wallet", "onchain", "provider"} else "all_upgrades", status="emergency_stopped", metadata={"stop_id": stop.stop_id}, root=root)
    return {"ok": True, "emergency_stop": record, "disabled_capabilities": ("byok", "wallet", "onchain", "provider", "future_execution")}


def emergency_stop_status(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    stops = tuple(record for record in _list_records(root, "emergency_stops") if record.get("agent_id") == agent_id and record.get("active") is True)
    return {"ok": True, "agent_id": agent_id, "active": bool(stops), "stops": stops, "emergency_stop_status": "active" if stops else "clear"}


def capability_summary(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    credentials = list_credential_bindings(agent_id, root=root)
    wallet = list_wallet_bindings(agent_id, root=root)
    onchain = tuple(record for record in _list_records(root, "onchain_intents") if record.get("agent_id") == agent_id)
    x402_routes = tuple(record for record in _list_records(root, "x402_routes") if record.get("agent_id") == agent_id)
    stopped = emergency_stop_status(agent_id, root=root)
    return {
        "ok": True,
        "agent_id": agent_id,
        "byok_capability_status": "bound" if any(record.get("status") == "active" for record in credentials) else "not_bound",
        "wallet_binding_status": "bound" if wallet else "not_bound",
        "onchain_upgrade_status": "prepared" if onchain else "not_prepared",
        "emergency_stop_status": stopped.get("emergency_stop_status", "clear"),
        "credential_count": len(credentials),
        "wallet_binding_count": len(wallet),
        "onchain_intent_count": len(onchain),
        "x402_route_count": len(x402_routes),
        "first_agent_requires_wallet_or_key": False,
        "no_private_key_required": True,
        "no_funds_moved": True,
        "no_broadcast": True,
        "mainnet_enabled": False,
    }


def x402_adapter_status() -> Mapping[str, Any]:
    installed = importlib.util.find_spec("x402") is not None
    return {
        "ok": True,
        "package": "x402",
        "installed": installed,
        "recommended_install": "python -m pip install \"x402[fastapi,httpx,evm]>=2.11.0\"",
        "node_install_express": "npm install @x402/express @x402/evm @x402/core",
        "coinbase_facilitator_url": X402_FACILITATORS["coinbase_cdp"]["facilitator_url"],
        "testnet_facilitator_url": X402_FACILITATORS["x402_org_testnet"]["facilitator_url"],
        "base_sepolia_network": "eip155:84532",
        "base_mainnet_network": "eip155:8453",
        "live_default": False,
        "settlement_enabled_default": False,
    }


def prepare_x402_payment_route(agent_id: str, resource: str, price: str, pay_to: str, *, facilitator: str = "x402_org_testnet", network: str = "eip155:84532", live_requested: bool = False, root: str | Path = ".") -> Mapping[str, Any]:
    facilitator_config = dict(X402_FACILITATORS.get(facilitator, X402_FACILITATORS["x402_org_testnet"]))
    if not _looks_like_address(pay_to):
        raise ValueError("pay_to must be a 0x-prefixed 20-byte receiving address")
    if network == "eip155:8453" and facilitator != "coinbase_cdp":
        raise ValueError("Base mainnet x402 requires the Coinbase CDP facilitator")
    mainnet = network == "eip155:8453"
    testnet_live_ready = bool(live_requested and not mainnet and facilitator == "x402_org_testnet")
    route = X402PaymentRoute(
        route_id=stable_id("x402_route", agent_id, resource, price, pay_to, facilitator, network),
        agent_id=agent_id,
        resource=resource,
        price=price,
        pay_to=pay_to.lower(),
        network=network,
        facilitator_url=str(facilitator_config.get("facilitator_url")),
        facilitator_provider=facilitator,
        mode="testnet_live_ready_relay_disabled" if testnet_live_ready else ("mainnet_config_ready_relay_disabled" if mainnet else "testnet_ready_relay_disabled"),
        status="prepared",
        settlement_enabled=False,
        testnet_live_ready=testnet_live_ready,
        no_funds_moved=True,
        no_broadcast=True,
        cdp_api_key_required=bool(facilitator_config.get("requires_cdp_api_key")),
    )
    record = route.as_record()
    record["x402_package_status"] = x402_adapter_status()
    record["payment_requirements_preview"] = {
        "scheme": "exact",
        "price": price,
        "network": network,
        "payTo": pay_to.lower(),
        "description": f"Access to {resource}",
        "mimeType": "application/json",
    }
    record["policy_state"] = {
        "approval_required": True,
        "live_requested": bool(live_requested),
        "mainnet_blocked": bool(mainnet),
        "relay_disabled_by_default": True,
        "testnet_live_ready": bool(testnet_live_ready),
        "flow_memory_execution_default": "prepare_only_no_relay",
    }
    return _write_record(root, "x402_routes", route.route_id, record)

def project_capabilities_to_agent_internet(agent_id: str, *, root: str | Path = ".") -> Mapping[str, Any]:
    summary = capability_summary(agent_id, root=root)
    updates = {
        "capability_status": {
            "byok": summary["byok_capability_status"],
            "wallet": summary["wallet_binding_status"],
            "onchain": summary["onchain_upgrade_status"],
            "emergency_stop": summary["emergency_stop_status"],
            "raw_api_key_exposed": False,
            "private_key_exposed": False,
        },
        "byok_capability_status": summary["byok_capability_status"],
        "wallet_binding_status": summary["wallet_binding_status"],
        "onchain_upgrade_status": summary["onchain_upgrade_status"],
        "emergency_stop_status": summary["emergency_stop_status"],
        "payment_capability": "dry_run_x402",
    }
    try:
        from flow_memory.agent_internet import get_agent_identity, update_agent_identity

        get_agent_identity(agent_id, root=root)
        projected = update_agent_identity(agent_id, updates, root=root)
        return {"ok": True, "agent_id": agent_id, "projected": True, "identity": projected, "capabilities": summary}
    except KeyError:
        return {"ok": False, "agent_id": agent_id, "projected": False, "reason": "agent_internet_identity_missing", "capabilities": summary}


def demo_capability_upgrade(root: str | Path = ".") -> Mapping[str, Any]:
    agent_id = "upgrade-demo-agent"
    try:
        from flow_memory.agent_internet import register_agent_identity

        register_agent_identity(agent_id, display_name="Upgrade Demo", root=root)
    except Exception:
        pass
    credential = create_credential_binding(agent_id, "openai", "env:OPENAI_API_KEY", budget_cap=5.0, root=root)
    byok_intent = simulate_byok_inference_intent(agent_id, "openai", "gpt-4.1-mini", "research", root=root)
    wallet = bind_wallet_identity(agent_id, "base_sepolia", "0x0000000000000000000000000000000000000000", root=root)
    prepared = prepare_onchain_upgrade(agent_id, "base_sepolia", "register_agent", root=root)
    simulated = simulate_onchain_upgrade(str(prepared["intent_id"]), root=root)
    approved = approve_onchain_upgrade(str(prepared["intent_id"]), root=root)
    sign_request = request_external_signature(str(prepared["intent_id"]), root=root)
    relay = relay_onchain_upgrade(str(prepared["intent_id"]), root=root)
    x402_route = prepare_x402_payment_route(
        agent_id,
        "agent_skill_match",
        "0.001",
        "0x0000000000000000000000000000000000000000",
        live_requested=True,
        root=root,
    )
    projection = project_capabilities_to_agent_internet(agent_id, root=root)
    emergency = activate_emergency_stop(agent_id, "all_upgrades", "demo stop", root=root)
    return {
        "ok": True,
        "agent_id": agent_id,
        "providers": provider_registry(),
        "credential": credential,
        "byok_intent": byok_intent,
        "wallet": wallet,
        "prepared": prepared,
        "simulated": simulated,
        "approved": approved,
        "sign_request": sign_request,
        "relay": relay,
        "projection": projection,
        "x402_route": x402_route,
        "emergency_stop": emergency,
        "summary": capability_summary(agent_id, root=root),
    }


def _stored_secret_ref(secret_ref: str, fingerprint: str) -> str:
    value = str(secret_ref or "")
    if value.startswith(("env:", "secret:", "secret://", "keyring:", "os-keyring:")):
        return value
    return f"fingerprint:{fingerprint}"


def _network_config(network: str) -> Mapping[str, Any]:
    key = str(network or "base_sepolia")
    if key not in NETWORKS:
        raise KeyError(f"unsupported wallet network: {network}")
    return NETWORKS[key]


def _looks_like_address(value: str) -> bool:
    text = str(value or "")
    return text.startswith("0x") and len(text) == 42 and all(char in "0123456789abcdefABCDEF" for char in text[2:])


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
        raise KeyError(f"unknown capability upgrade {category} record: {key}")
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
