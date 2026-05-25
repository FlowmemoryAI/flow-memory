"""Provider quote contract validation for Flow Memory Compute Market onboarding."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.compute_market.models import SUPPORTED_UNIT_TYPES
from flow_memory.compute_market.storage import utc_now_iso
from flow_memory.crypto.asymmetric import ED25519_ALGORITHM, LOCAL_TEST_ASYMMETRIC_ALGORITHM, LocalTestVerifier, PublicKeyRecord
from flow_memory.crypto.ed25519 import Ed25519Verifier

_REQUIRED_FIELDS = (
    "provider_id",
    "route_id",
    "quote_id",
    "unit_type",
    "unit_price",
    "estimated_units",
    "estimated_total_cost",
    "currency_or_asset",
    "quote_ttl_seconds",
    "expires_at",
    "confidence",
    "capacity_available",
    "settlement_modes",
    "dry_run_supported",
    "assumptions",
)

_UNSAFE_FIELDS = (
    "private_key",
    "secret_key",
    "seed_phrase",
    "seed phrase",
    "mnemonic",
    "wallet_private_key",
    "broadcast",
    "live_settlement",
    "sendTransaction",
    "signTransaction",
    "transfer",
    "withdraw",
    "deposit",
    "custody",
    "mainnet settlement",
)


@dataclass(frozen=True)
class ProviderContractValidation:
    ok: bool
    error_codes: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_record(self) -> dict[str, object]:
        return {"ok": self.ok, "error_codes": self.error_codes, "warnings": self.warnings}


@dataclass(frozen=True)
class ProviderQuoteContract:
    provider_id: str = ""
    allowed_assets: tuple[str, ...] = ()
    allowed_networks: tuple[str, ...] = ()
    allow_unknown_unit_type: bool = False
    public_key: str | Mapping[str, Any] = ""
    max_response_bytes: int = 65_536

    def validate(self, quote: Mapping[str, Any]) -> ProviderContractValidation:
        errors: list[str] = []
        warnings: list[str] = []
        encoded = json.dumps(quote, sort_keys=True, default=str).encode("utf-8")
        if len(encoded) > self.max_response_bytes:
            errors.append("oversized_response")
        for field in _REQUIRED_FIELDS:
            if field not in quote:
                errors.append(f"missing_{field}")
        for key, value in _walk(quote):
            lowered_key = key.lower()
            lowered_value = value.lower() if isinstance(value, str) else ""
            if any(token.lower() in lowered_key or token.lower() in lowered_value for token in _UNSAFE_FIELDS):
                errors.append("unsafe_payload")
                break
        if self.provider_id and str(quote.get("provider_id", "")) != self.provider_id:
            errors.append("provider_id_mismatch")
        if not str(quote.get("route_id", "")):
            errors.append("missing_route_id")
        unit_type = str(quote.get("unit_type", ""))
        if unit_type not in SUPPORTED_UNIT_TYPES and not self.allow_unknown_unit_type:
            errors.append("unsupported_unit_type")
        unit_price = _float_or_none(quote.get("unit_price"))
        total_cost = _float_or_none(quote.get("estimated_total_cost"))
        if unit_price is None:
            errors.append("unknown_price")
        elif unit_price < 0:
            errors.append("negative_price")
        if total_cost is None:
            errors.append("unknown_total_cost")
        elif total_cost < 0:
            errors.append("negative_total_cost")
        ttl = _int_or_none(quote.get("quote_ttl_seconds"))
        if ttl is None or ttl <= 0:
            errors.append("missing_quote_ttl")
        expires_at = str(quote.get("expires_at", ""))
        if not _looks_like_timestamp(expires_at):
            errors.append("malformed_expires_at")
        elif expires_at <= utc_now_iso():
            errors.append("expired_quote")
        if quote.get("stale") is True:
            errors.append("stale_quote")
        if quote.get("dry_run_supported") is not True:
            errors.append("dry_run_not_supported")
        if quote.get("requires_live_settlement") is True:
            errors.append("live_settlement_required")
        if quote.get("private_key_required") is True:
            errors.append("private_key_required")
        if quote.get("broadcast_required") is True or quote.get("broadcast") is True:
            errors.append("broadcast_required")
        asset = str(quote.get("currency_or_asset", quote.get("payment_asset", "")))
        if self.allowed_assets and asset not in self.allowed_assets:
            errors.append("disallowed_asset")
        network = str(quote.get("network", ""))
        if self.allowed_networks and network and network not in self.allowed_networks:
            errors.append("disallowed_network")
        if not isinstance(quote.get("settlement_modes", ()), (tuple, list)):
            errors.append("settlement_modes_malformed")
        if "policy" in quote or "policy_override" in quote or "ignore_policy" in quote:
            errors.append("policy_override_attempt")
        signature_present = "signature" in quote or "verification" in quote
        if not signature_present:
            warnings.append("unsigned_quote")
        elif self.public_key and not verify_provider_quote_signature(quote, self.public_key):
            errors.append("invalid_signature")
        return ProviderContractValidation(ok=not errors, error_codes=tuple(dict.fromkeys(errors)), warnings=tuple(warnings))


def validate_provider_quote_contract(
    quote: Mapping[str, Any],
    *,
    provider_id: str = "",
    allowed_assets: tuple[str, ...] = (),
    allowed_networks: tuple[str, ...] = (),
    allow_unknown_unit_type: bool = False,
    max_response_bytes: int = 65_536,
    public_key: str | Mapping[str, Any] = "",
) -> ProviderContractValidation:
    return ProviderQuoteContract(
        provider_id=provider_id,
        allowed_assets=allowed_assets,
        allowed_networks=allowed_networks,
        allow_unknown_unit_type=allow_unknown_unit_type,
        max_response_bytes=max_response_bytes,
        public_key=public_key,
    ).validate(quote)


def validate_provider_contract_file(path: str | Path, *, provider_id: str = "") -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    quote = payload.get("quote", payload) if isinstance(payload, Mapping) else {}
    if not isinstance(quote, Mapping):
        return {"ok": False, "error_codes": ("invalid_json_shape",), "path": str(path)}
    result = validate_provider_quote_contract(quote, provider_id=provider_id or str(quote.get("provider_id", "")))
    return {"ok": result.ok, "validation": result.as_record(), "path": str(path)}


def verify_provider_quote_signature(quote: Mapping[str, Any], public_key: str | Mapping[str, Any]) -> bool:
    envelope = quote.get("signature") or quote.get("verification")
    if not isinstance(envelope, Mapping):
        return False
    record = dict(envelope)
    public = _public_key_record(public_key, record)
    if public is None:
        return False
    signed_payload = {
        key: value
        for key, value in quote.items()
        if key not in {"signature", "verification"}
    }
    if public.algorithm == LOCAL_TEST_ASYMMETRIC_ALGORITHM:
        return LocalTestVerifier(public).verify(signed_payload, record).ok
    if public.algorithm == ED25519_ALGORITHM:
        return Ed25519Verifier(public).verify(signed_payload, record).ok
    return False


def _public_key_record(public_key: str | Mapping[str, Any], envelope: Mapping[str, Any]) -> PublicKeyRecord | None:
    if isinstance(public_key, Mapping):
        key_id = str(public_key.get("key_id") or envelope.get("key_id") or "")
        algorithm = str(public_key.get("algorithm") or envelope.get("algorithm") or "")
        key_value = str(public_key.get("public_key") or public_key.get("key") or "")
        local_only = bool(public_key.get("local_only", algorithm == LOCAL_TEST_ASYMMETRIC_ALGORITHM))
    else:
        key_id = str(envelope.get("key_id") or "")
        algorithm = str(envelope.get("algorithm") or ED25519_ALGORITHM)
        key_value = str(public_key or envelope.get("public_key") or "")
        local_only = algorithm == LOCAL_TEST_ASYMMETRIC_ALGORITHM
    if not key_id or not algorithm or not key_value:
        return None
    return PublicKeyRecord(key_id=key_id, algorithm=algorithm, public_key=key_value, local_only=local_only)

def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _looks_like_timestamp(value: str) -> bool:
    return bool(value and "T" in value and value.endswith("Z"))


def _walk(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, Mapping):
        items: list[tuple[str, object]] = []
        for key, nested in value.items():
            items.append((str(key), nested))
            items.extend(_walk(nested))
        return tuple(items)
    if isinstance(value, (tuple, list)):
        items = []
        for nested in value:
            items.extend(_walk(nested))
        return tuple(items)
    return ()
