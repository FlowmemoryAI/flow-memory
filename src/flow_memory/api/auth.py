"""Local API auth seams."""

from __future__ import annotations

import secrets
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from flow_memory.api.signed_requests import verify_request
from flow_memory.api.scopes import KNOWN_SCOPES
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


def issue_api_key_record(
    payload: Mapping[str, Any],
    *,
    api_key: str | None = None,
) -> Mapping[str, Any]:
    prefix = str(payload.get("key_prefix") or "fmk_")
    if not prefix or any(character.isspace() for character in prefix):
        raise ValueError("key_prefix must be non-empty and contain no whitespace")
    secret = api_key or f"{prefix}{secrets.token_urlsafe(32)}"
    if not secret.startswith(prefix):
        raise ValueError("api key must start with key_prefix")
    key_id = str(payload.get("key_id") or f"key_{secrets.token_hex(8)}")
    tenant_id = str(payload.get("tenant_id") or "")
    principal = str(payload.get("principal") or payload.get("created_by") or "api-key")
    scopes = _parse_scopes(payload.get("scopes", ()))
    invalid_scopes = tuple(scope for scope in scopes if scope not in KNOWN_SCOPES)
    if invalid_scopes:
        raise ValueError(f"unknown API scopes: {', '.join(invalid_scopes)}")
    now = int(time.time())
    record = {
        "key_id": key_id,
        "key_prefix": prefix,
        "key_hash": api_key_hash(secret),
        "tenant_id": tenant_id,
        "workspace_id": str(payload.get("workspace_id", "")),
        "principal": principal,
        "scopes": scopes,
        "enabled": True,
        "status": "active",
        "created_by": str(payload.get("created_by", principal)),
        "created_at_epoch": now,
        "rotation_counter": int(payload.get("rotation_counter", 0) or 0),
    }
    previous_key_id = str(payload.get("previous_key_id", ""))
    if previous_key_id:
        record["previous_key_id"] = previous_key_id
    return {"api_key": secret, "record": record}


def rotate_api_key_record(
    existing: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
    *,
    api_key: str | None = None,
) -> Mapping[str, Any]:
    update = dict(payload or {})
    previous_key_id = str(existing.get("key_id", ""))
    if not previous_key_id:
        raise ValueError("existing api key record missing key_id")
    now = int(time.time())
    disabled = {
        **dict(existing),
        "enabled": False,
        "status": "rotated",
        "rotated_at_epoch": now,
        "rotation_reason": str(update.get("reason", "rotation")),
    }
    next_payload = {
        "key_prefix": str(update.get("key_prefix", existing.get("key_prefix", "fmk_"))),
        "tenant_id": str(update.get("tenant_id", existing.get("tenant_id", ""))),
        "workspace_id": str(update.get("workspace_id", existing.get("workspace_id", ""))),
        "principal": str(update.get("principal", existing.get("principal", "api-key"))),
        "scopes": update.get("scopes", existing.get("scopes", ())),
        "created_by": str(update.get("created_by", existing.get("principal", "api-key"))),
        "previous_key_id": previous_key_id,
        "rotation_counter": int(existing.get("rotation_counter", 0) or 0) + 1,
    }
    if update.get("key_id"):
        next_payload["key_id"] = str(update["key_id"])
    issued = issue_api_key_record(next_payload, api_key=api_key)
    return {"previous_record": disabled, "record": issued["record"], "api_key": issued["api_key"]}


def disable_api_key_record(record: Mapping[str, Any], *, reason: str = "operator_requested") -> Mapping[str, Any]:
    if not record.get("key_id"):
        raise ValueError("api key record missing key_id")
    return {
        **dict(record),
        "enabled": False,
        "status": "disabled",
        "disabled_at_epoch": int(time.time()),
        "disabled_reason": reason,
    }


def public_api_key_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    public = {str(key): value for key, value in record.items() if key not in {"key_hash", "api_key"}}
    public["key_hash_configured"] = bool(record.get("key_hash"))
    return public


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
