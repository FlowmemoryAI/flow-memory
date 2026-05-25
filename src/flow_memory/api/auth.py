"""Local API auth seams."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from flow_memory.api.signed_requests import verify_request
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope


@dataclass(frozen=True)
class ApiKeyIdentity:
    key_id: str = ""
    tenant_id: str = ""
    principal: str = ""
    scopes: tuple[str, ...] = ()
    key_prefix: str = ""


@dataclass(frozen=True)
class ApiAuthConfig:
    api_key: str = ""
    require_signed_requests: bool = False
    api_key_records: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ApiAuthDecision:
    ok: bool
    reasons: tuple[str, ...] = ()
    tenant_id: str = ""
    principal: str = ""
    scopes: tuple[str, ...] = ()
    key_id: str = ""


def require_api_key(headers: Mapping[str, str], config: ApiAuthConfig) -> bool:
    if not config.api_key and not config.api_key_records:
        return True
    return resolve_api_key(headers, config) is not None


def resolve_api_key(headers: Mapping[str, str], config: ApiAuthConfig) -> ApiKeyIdentity | None:
    supplied = _header(headers, "x-flow-memory-api-key")
    if not supplied:
        return None
    if config.api_key and supplied == config.api_key:
        return ApiKeyIdentity(key_id="legacy", principal=_header(headers, "x-flow-memory-principal") or "api-key", tenant_id=_header(headers, "x-flow-memory-tenant"), scopes=())
    supplied_hash = api_key_hash(supplied)
    for record in config.api_key_records:
        if not _truthy(record.get("enabled", True)):
            continue
        expected_hash = str(record.get("key_hash", ""))
        prefix = str(record.get("key_prefix", ""))
        if expected_hash and _constant_time_equal(supplied_hash, expected_hash) and (not prefix or supplied.startswith(prefix)):
            return ApiKeyIdentity(
                key_id=str(record.get("key_id", "")),
                tenant_id=str(record.get("tenant_id", "")),
                principal=str(record.get("principal", record.get("created_by", "api-key"))),
                scopes=_parse_scopes(record.get("scopes", ())),
                key_prefix=prefix,
            )
    return None


def api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def authorize_request(
    headers: Mapping[str, str],
    config: ApiAuthConfig,
    *,
    method: str = "GET",
    path: str = "/",
    payload: Mapping[str, Any] | None = None,
    signature: SignatureEnvelope | None = None,
    signature_key: LocalKeyPair | None = None,
) -> ApiAuthDecision:
    reasons: list[str] = []
    identity = resolve_api_key(headers, config)
    if (config.api_key or config.api_key_records) and identity is None:
        reasons.append("missing or invalid API key")
    if config.require_signed_requests:
        if signature is None or signature_key is None:
            reasons.append("signed request required")
        elif not verify_request(method, path, payload or {}, signature, signature_key):
            reasons.append("invalid request signature")
    return ApiAuthDecision(
        ok=not reasons,
        reasons=tuple(reasons),
        tenant_id=identity.tenant_id if identity else "",
        principal=identity.principal if identity else "",
        scopes=identity.scopes if identity else (),
        key_id=identity.key_id if identity else "",
    )


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""


def _parse_scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: Sequence[str] = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = tuple(str(item) for item in value)
    else:
        parts = ()
    return tuple(sorted({part.strip() for part in parts if part.strip()}))


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "disabled"}
    return bool(value)


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)
