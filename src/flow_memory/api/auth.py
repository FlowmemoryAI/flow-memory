"""Local API auth seams."""

from __future__ import annotations

import time
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
    enable_nonce_check: bool = False
    max_request_age_seconds: int = 300


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
    if config.enable_nonce_check and identity is not None:
        reasons.extend(_nonce_replay_reasons(headers, identity=identity, max_age_seconds=config.max_request_age_seconds))
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


_NONCE_CACHE: dict[str, float] = {}


def _nonce_replay_reasons(headers: Mapping[str, str], *, identity: ApiKeyIdentity, max_age_seconds: int) -> tuple[str, ...]:
    reasons: list[str] = []
    nonce = _header(headers, "x-flow-memory-nonce").strip()
    timestamp = _header(headers, "x-flow-memory-timestamp").strip()
    if not nonce:
        reasons.append("missing request nonce")
    if not timestamp:
        reasons.append("missing request timestamp")
    if reasons:
        return tuple(reasons)
    now = time.time()
    try:
        timestamp_seconds = float(timestamp)
    except ValueError:
        return ("invalid request timestamp",)
    max_age = max(1, int(max_age_seconds))
    if abs(now - timestamp_seconds) > max_age:
        return ("stale request timestamp",)
    _purge_nonce_cache(now=now, max_age_seconds=max_age)
    namespace = identity.key_id or identity.principal or identity.tenant_id or "legacy"
    cache_key = f"{namespace}:{nonce}"
    if cache_key in _NONCE_CACHE:
        return ("replayed request nonce",)
    _NONCE_CACHE[cache_key] = timestamp_seconds
    return ()


def _purge_nonce_cache(*, now: float, max_age_seconds: int) -> None:
    stale_before = now - max_age_seconds
    for key, seen_at in tuple(_NONCE_CACHE.items()):
        if seen_at < stale_before:
            _NONCE_CACHE.pop(key, None)
