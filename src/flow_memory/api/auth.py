"""Local API auth seams."""

from __future__ import annotations

import base64
import json
import hmac
import secrets
import time
import hashlib
import ssl
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from flow_memory.api.signed_requests import verify_request
from flow_memory.api.scopes import KNOWN_SCOPES
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope

class NonceReplayStore(Protocol):
    """Atomic nonce replay guard shared by API server instances."""

    def claim(self, cache_key: str, *, timestamp_seconds: float, ttl_seconds: int) -> bool:
        """Return True when the nonce key was newly claimed."""


class NonceStoreUnavailable(RuntimeError):
    """Raised when a fail-closed nonce replay backend cannot be reached."""


@dataclass
class LocalNonceReplayStore:
    """In-process nonce replay guard for local and single-instance deployments."""

    seen: dict[str, float] = field(default_factory=dict)

    def claim(self, cache_key: str, *, timestamp_seconds: float, ttl_seconds: int) -> bool:
        self.purge(now=time.time(), max_age_seconds=ttl_seconds)
        if cache_key in self.seen:
            return False
        self.seen[cache_key] = timestamp_seconds
        return True

    def purge(self, *, now: float, max_age_seconds: int) -> None:
        stale_before = now - max(1, int(max_age_seconds))
        for key, seen_at in tuple(self.seen.items()):
            if seen_at < stale_before:
                self.seen.pop(key, None)


@dataclass
class RedisNonceReplayStore:
    """Redis-backed nonce replay guard for horizontally scaled public API nodes."""

    redis_url: str
    prefix: str = "flow-memory:api"
    fail_closed: bool = True
    require_tls: bool = False
    verify_tls: bool = True
    client: Any | None = None

    def claim(self, cache_key: str, *, timestamp_seconds: float, ttl_seconds: int) -> bool:
        try:
            redis_client = self._client()
            redis_key = self._redis_key(cache_key)
            claimed = redis_client.set(redis_key, str(timestamp_seconds), nx=True, ex=max(1, int(ttl_seconds)))
            return bool(claimed)
        except Exception as exc:
            if self.fail_closed:
                raise NonceStoreUnavailable("nonce replay backend unavailable") from exc
            return True

    def _redis_key(self, cache_key: str) -> str:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return f"{self.prefix}:nonce:{digest}"

    def _client(self) -> Any:
        if not self.redis_url:
            raise RuntimeError("redis_url is required")
        if self.require_tls and not self.redis_url.startswith("rediss://"):
            raise RuntimeError("managed Redis nonce replay requires a rediss:// TLS URL")
        if self.client is not None:
            return self.client
        try:
            import redis
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Redis nonce replay requires optional dependency: redis") from exc
        kwargs: dict[str, object] = {"decode_responses": True}
        if self.verify_tls and self.redis_url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
        self.client = redis.Redis.from_url(self.redis_url, **kwargs)
        return self.client

@dataclass(frozen=True)
class ApiKeyIdentity:
    key_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    principal: str = ""
    scopes: tuple[str, ...] = ()
    key_prefix: str = ""
    token_id: str = ""
    issued_at_epoch: float = 0.0


@dataclass(frozen=True)
class ApiAuthConfig:
    api_key: str = ""
    api_key_scopes: tuple[str, ...] = ()
    require_signed_requests: bool = False
    api_key_records: tuple[Mapping[str, Any], ...] = ()
    enable_nonce_check: bool = False
    max_request_age_seconds: int = 300
    jwt_hs256_secret: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = ""
    jwt_leeway_seconds: int = 60
    jwt_require_tenant: bool = False
    nonce_replay_store: NonceReplayStore | None = None

KNOWN_AUTH_ROLES = frozenset({
    "admin",
    "auditor",
    "billing",
    "member",
    "policy-admin",
    "provider",
    "provider-admin",
    "settlement-admin",
    "viewer",
})
ROLE_SCOPE_MAP: Mapping[str, tuple[str, ...]] = {
    "admin": ("api:admin",),
    "auditor": ("api:audit", "compute:audit", "compute:read"),
    "billing": ("compute:billing", "compute:read"),
    "member": ("api:read", "api:write", "compute:read", "compute:plan", "compute:execute"),
    "policy-admin": ("compute:policy-admin", "compute:read"),
    "provider": ("compute:read",),
    "provider-admin": ("compute:provider-admin", "compute:read"),
    "settlement-admin": ("compute:settlement-admin", "compute:read"),
    "viewer": ("api:read", "compute:read"),
}


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    tenant_id: str
    workspace_id: str
    email: str
    display_name: str
    roles: tuple[str, ...]
    enabled: bool
    created_at_epoch: int
    created_by: str

    def as_record(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class WorkspaceRecord:
    workspace_id: str
    tenant_id: str
    org_name: str
    display_name: str
    enabled: bool
    created_at_epoch: int
    created_by: str
    metadata: Mapping[str, Any]

    def as_record(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class MembershipRecord:
    workspace_id: str
    tenant_id: str
    user_id: str
    role: str
    added_at_epoch: int
    added_by: str
    enabled: bool = True

    def as_record(self) -> dict[str, Any]:
        return dict(self.__dict__)

@dataclass(frozen=True)
class ApiAuthDecision:
    ok: bool
    reasons: tuple[str, ...] = ()
    tenant_id: str = ""
    workspace_id: str = ""
    principal: str = ""
    scopes: tuple[str, ...] = ()
    key_id: str = ""


def require_api_key(headers: Mapping[str, str], config: ApiAuthConfig) -> bool:
    if not config.api_key and not config.api_key_records and not config.jwt_hs256_secret:
        return True
    return authorize_request(headers, config).ok


def resolve_api_key(headers: Mapping[str, str], config: ApiAuthConfig) -> ApiKeyIdentity | None:
    identity, _ = _resolve_api_key_with_reasons(headers, config)
    return identity


def _resolve_api_key_with_reasons(
    headers: Mapping[str, str],
    config: ApiAuthConfig,
) -> tuple[ApiKeyIdentity | None, tuple[str, ...]]:
    supplied = _header(headers, "x-flow-memory-api-key")
    if not supplied:
        return None, ()
    if config.api_key and supplied == config.api_key:
        scopes = _parse_scopes(config.api_key_scopes)
        invalid_scopes = tuple(scope for scope in scopes if scope not in KNOWN_SCOPES)
        if invalid_scopes:
            return None, (f"api key configuration contains unknown scope: {', '.join(invalid_scopes)}",)
        return (
            ApiKeyIdentity(
                key_id="legacy",
                principal=_header(headers, "x-flow-memory-principal") or "api-key",
                tenant_id=_header(headers, "x-flow-memory-tenant"),
                workspace_id=_header(headers, "x-flow-memory-workspace"),
                scopes=scopes,
            ),
            (),
        )
    supplied_hash = api_key_hash(supplied)
    for record in config.api_key_records:
        if not _truthy(record.get("enabled", True)):
            continue
        expected_hash = str(record.get("key_hash", ""))
        prefix = str(record.get("key_prefix", ""))
        if expected_hash and _constant_time_equal(supplied_hash, expected_hash) and (not prefix or supplied.startswith(prefix)):
            try:
                scopes = _api_key_record_scopes(record)
            except ValueError as exc:
                return None, (f"api key record invalid: {exc}",)
            invalid_scopes = tuple(scope for scope in scopes if scope not in KNOWN_SCOPES)
            if invalid_scopes:
                return None, (
                    f"api key record contains unknown scope: {', '.join(invalid_scopes)}",
                )
            return (
                ApiKeyIdentity(
                    key_id=str(record.get("key_id", "")),
                    tenant_id=str(record.get("tenant_id", "")),
                    workspace_id=str(record.get("workspace_id", "")),
                    principal=str(record.get("principal", record.get("created_by", "api-key"))),
                    scopes=scopes,
                    key_prefix=prefix,
                ),
                (),
            )
    return None, ()


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
    explicit_scopes = _parse_scopes(payload.get("scopes", ()))
    roles = _parse_api_key_roles(payload.get("roles", ()))
    scopes = tuple(sorted({*explicit_scopes, *_scopes_from_roles(roles)}))
    invalid_scopes = tuple(scope for scope in explicit_scopes if scope not in KNOWN_SCOPES)
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
        "explicit_scopes": explicit_scopes,
        "roles": roles,
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
        "scopes": update.get("scopes", _explicit_api_key_scopes(existing)),
        "roles": update.get("roles", existing.get("roles", ())),
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


def create_user_record(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    email = str(payload.get("email", "")).strip().lower()
    if not email or "@" not in email:
        raise ValueError("email is required")
    roles = _parse_roles(payload.get("roles", ("viewer",)))
    now = int(time.time())
    return UserRecord(
        user_id=str(payload.get("user_id") or f"user_{secrets.token_hex(8)}"),
        tenant_id=str(payload.get("tenant_id", "")),
        workspace_id=str(payload.get("workspace_id", "")),
        email=email,
        display_name=str(payload.get("display_name", email)).strip() or email,
        roles=roles,
        enabled=True,
        created_at_epoch=now,
        created_by=str(payload.get("created_by", payload.get("principal", "api-admin"))),
    ).as_record()


def update_user_record(existing: Mapping[str, Any], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    updated = dict(existing)
    if "email" in payload:
        email = str(payload.get("email", "")).strip().lower()
        if not email or "@" not in email:
            raise ValueError("email is required")
        updated["email"] = email
    if "display_name" in payload:
        updated["display_name"] = str(payload.get("display_name", "")).strip()
    if "roles" in payload:
        updated["roles"] = _parse_roles(payload.get("roles", ()))
    updated["updated_at_epoch"] = int(time.time())
    updated["updated_by"] = str(payload.get("updated_by", payload.get("principal", "api-admin")))
    return updated


def disable_user_record(record: Mapping[str, Any], *, reason: str = "operator_requested") -> Mapping[str, Any]:
    if not _truthy(record.get("enabled", True)):
        raise ValueError("user is already disabled")
    return {**dict(record), "enabled": False, "status": "disabled", "disabled_reason": reason, "disabled_at_epoch": int(time.time())}


def create_workspace_record(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    org_name = str(payload.get("org_name", payload.get("organization", ""))).strip()
    display_name = str(payload.get("display_name", org_name)).strip() or org_name
    if not org_name:
        raise ValueError("org_name is required")
    metadata = payload.get("metadata", {})
    return WorkspaceRecord(
        workspace_id=str(payload.get("workspace_id") or f"ws_{secrets.token_hex(8)}"),
        tenant_id=str(payload.get("tenant_id", "")),
        org_name=org_name,
        display_name=display_name,
        enabled=True,
        created_at_epoch=int(time.time()),
        created_by=str(payload.get("created_by", payload.get("principal", "api-admin"))),
        metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
    ).as_record()


def update_workspace_record(existing: Mapping[str, Any], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    updated = dict(existing)
    if "org_name" in payload:
        org_name = str(payload.get("org_name", "")).strip()
        if not org_name:
            raise ValueError("org_name is required")
        updated["org_name"] = org_name
    if "display_name" in payload:
        updated["display_name"] = str(payload.get("display_name", "")).strip()
    if "metadata" in payload:
        metadata = payload.get("metadata", {})
        updated["metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
    updated["updated_at_epoch"] = int(time.time())
    updated["updated_by"] = str(payload.get("updated_by", payload.get("principal", "api-admin")))
    return updated


def disable_workspace_record(record: Mapping[str, Any], *, reason: str = "operator_requested") -> Mapping[str, Any]:
    if not _truthy(record.get("enabled", True)):
        raise ValueError("workspace is already disabled")
    return {**dict(record), "enabled": False, "status": "disabled", "disabled_reason": reason, "disabled_at_epoch": int(time.time())}


def create_membership_record(workspace_id: str, user_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MembershipRecord(
        workspace_id=workspace_id,
        tenant_id=str(payload.get("tenant_id", "")),
        user_id=user_id,
        role=validate_role_name(str(payload.get("role", "member"))),
        added_at_epoch=int(time.time()),
        added_by=str(payload.get("added_by", payload.get("principal", "api-admin"))),
    ).as_record()


def public_user_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _public_auth_record(record)


def public_workspace_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _public_auth_record(record)


def public_membership_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _public_auth_record(record)


def validate_role_name(role: str) -> str:
    normalized = role.strip()
    if not normalized:
        raise ValueError("role must be non-empty")
    if normalized != normalized.lower() or any(character.isspace() for character in normalized):
        raise ValueError("role must be lowercase and contain no whitespace")
    if normalized not in KNOWN_AUTH_ROLES:
        raise ValueError(f"unknown role: {normalized}")
    return normalized


def is_valid_role(role: str) -> bool:
    try:
        validate_role_name(role)
    except ValueError:
        return False
    return True


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
    api_reasons: tuple[str, ...] = ()
    api_identity, api_reasons = _resolve_api_key_with_reasons(headers, config)
    jwt_identity, jwt_reasons = resolve_bearer_jwt(headers, config)
    identity = api_identity or jwt_identity
    signature_nonce = ""
    signature_timestamp = ""
    if config.enable_nonce_check and identity is not None:
        signature_nonce, signature_timestamp = _request_nonce_timestamp(headers, identity)
    auth_configured = bool(config.api_key or config.api_key_records or config.jwt_hs256_secret)
    if auth_configured and identity is None:
        if api_reasons:
            reasons.extend(api_reasons)
        elif jwt_reasons:
            reasons.extend(jwt_reasons)
        else:
            reasons.append(
                "missing or invalid API key or bearer token"
                if config.jwt_hs256_secret
                else "missing or invalid API key"
            )
    if config.require_signed_requests:
        if signature is None or signature_key is None:
            reasons.append("signed request required")
        elif not verify_request(method, path, payload or {}, signature, signature_key, nonce=signature_nonce, timestamp=signature_timestamp):
            reasons.append("invalid request signature")
    if config.enable_nonce_check and identity is not None and not reasons:
        reasons.extend(
            _nonce_replay_reasons(
                headers,
                identity=identity,
                max_age_seconds=config.max_request_age_seconds,
                replay_store=config.nonce_replay_store,
            )
        )
    return ApiAuthDecision(
        ok=not reasons,
        reasons=tuple(reasons),
        tenant_id=identity.tenant_id if identity else "",
        workspace_id=identity.workspace_id if identity else "",
        principal=identity.principal if identity else "",
        scopes=identity.scopes if identity else (),
        key_id=identity.key_id if identity else "",
    )

def resolve_bearer_jwt(headers: Mapping[str, str], config: ApiAuthConfig) -> tuple[ApiKeyIdentity | None, tuple[str, ...]]:
    if not config.jwt_hs256_secret:
        return None, ()
    authorization = _header(headers, "authorization")
    if not authorization.lower().startswith("bearer "):
        return None, ("missing bearer token",)
    token = authorization.split(None, 1)[1].strip()
    if not token:
        return None, ("missing bearer token",)
    parts = token.split(".")
    if len(parts) != 3:
        return None, ("malformed bearer token",)
    try:
        header = _jwt_json_segment(parts[0])
        claims = _jwt_json_segment(parts[1])
        signature = _b64url_decode(parts[2])
    except ValueError as exc:
        return None, (str(exc),)
    if str(header.get("alg", "")) != "HS256":
        return None, ("unsupported jwt alg",)
    signed = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(config.jwt_hs256_secret.encode("utf-8"), signed, "sha256").digest()
    if not hmac.compare_digest(signature, expected):
        return None, ("invalid bearer token signature",)
    claim_errors = _jwt_claim_errors(claims, config)
    if claim_errors:
        return None, claim_errors
    subject = str(claims.get("sub", ""))
    if not subject:
        return None, ("jwt sub required",)
    tenant_id = str(claims.get("tenant_id", claims.get("org_id", "")))
    workspace_id = str(claims.get("workspace_id", claims.get("workspace", "")))
    if config.jwt_require_tenant and not tenant_id:
        return None, ("jwt tenant required",)
    scopes = _jwt_scopes(claims)
    return (
        ApiKeyIdentity(
            key_id=str(header.get("kid", "jwt")),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            principal=subject,
            scopes=scopes,
            token_id=str(claims.get("jti", "")),
            issued_at_epoch=_numeric_claim(claims.get("iat")) or 0.0,
            key_prefix="bearer",
        ),
        (),
    )

def _b64url_decode(segment: str) -> bytes:
    try:
        padding = "=" * ((4 - len(segment) % 4) % 4)
        return base64.urlsafe_b64decode((segment + padding).encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("malformed bearer token") from exc


def _jwt_json_segment(segment: str) -> Mapping[str, Any]:
    try:
        decoded = json.loads(_b64url_decode(segment).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed bearer token") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("malformed bearer token")
    return decoded


def _jwt_claim_errors(claims: Mapping[str, Any], config: ApiAuthConfig) -> tuple[str, ...]:
    errors: list[str] = []
    now = time.time()
    leeway = max(0, int(config.jwt_leeway_seconds))
    exp = _numeric_claim(claims.get("exp"))
    if exp is None:
        errors.append("jwt exp required")
    elif exp + leeway < now:
        errors.append("expired bearer token")
    iat = _numeric_claim(claims.get("iat"))
    if iat is None:
        errors.append("jwt iat required")
    elif iat - leeway > now:
        errors.append("bearer token issued in the future")
    if exp is not None and iat is not None and exp < iat:
        errors.append("jwt exp before iat")
    nbf = _numeric_claim(claims.get("nbf"))
    if nbf is not None and nbf - leeway > now:
        errors.append("bearer token not yet valid")
    if config.jwt_issuer and str(claims.get("iss", "")) != config.jwt_issuer:
        errors.append("jwt issuer mismatch")
    if config.jwt_audience and not _jwt_audience_matches(claims.get("aud"), config.jwt_audience):
        errors.append("jwt audience mismatch")
    return tuple(errors)


def _numeric_claim(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _jwt_audience_matches(value: object, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return expected in {str(item) for item in value}
    return False


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""


def _api_key_record_scopes(record: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = _parse_scopes(record.get("scopes", ()))
    roles = _parse_api_key_roles(record.get("roles", ()))
    role_scopes = _scopes_from_roles(roles)
    return tuple(sorted({*explicit, *role_scopes}))


def _explicit_api_key_scopes(record: Mapping[str, Any]) -> tuple[str, ...]:
    stored_explicit = record.get("explicit_scopes")
    if stored_explicit is not None:
        return _parse_scopes(stored_explicit)
    role_scopes = set(_scopes_from_roles(record.get("roles", ())))
    return tuple(scope for scope in _parse_scopes(record.get("scopes", ())) if scope not in role_scopes)


def _parse_api_key_roles(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: Sequence[str] = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = tuple(str(item) for item in value)
    else:
        parts = ()
    return tuple(sorted({validate_role_name(part) for part in parts if part.strip()}))

def _jwt_scopes(claims: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = _parse_scopes(claims.get("scope", claims.get("scp", ())))
    role_claim = claims.get("flow_memory_roles", claims.get("roles", claims.get("role", ())))
    role_scopes = _scopes_from_roles(role_claim)
    return tuple(sorted({*explicit, *role_scopes}))


def _scopes_from_roles(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: Sequence[str] = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = tuple(str(item) for item in value)
    else:
        parts = ()
    scopes: set[str] = set()
    for part in parts:
        role = part.strip().lower()
        scopes.update(ROLE_SCOPE_MAP.get(role, ()))
    return tuple(sorted(scopes))


def _parse_scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: Sequence[str] = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = tuple(str(item) for item in value)
    else:
        parts = ()
    return tuple(sorted({part.strip() for part in parts if part.strip()}))


def _parse_roles(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: Sequence[str] = value.replace(",", " ").split()
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = tuple(str(item) for item in value)
    else:
        parts = ()
    roles = tuple(validate_role_name(part) for part in parts if part.strip())
    return roles or ("viewer",)


def _public_auth_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    internal = {"key_hash", "api_key", "password", "secret", "token"}
    return {str(key): value for key, value in record.items() if str(key) not in internal}


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "disabled"}
    return bool(value)


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


_NONCE_CACHE: dict[str, float] = {}
_LOCAL_NONCE_REPLAY_STORE = LocalNonceReplayStore(_NONCE_CACHE)


def _nonce_replay_reasons(
    headers: Mapping[str, str],
    *,
    identity: ApiKeyIdentity,
    max_age_seconds: int,
    replay_store: NonceReplayStore | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    nonce, timestamp = _request_nonce_timestamp(headers, identity)
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
    namespace = "|".join(
        (
            identity.tenant_id or "tenant:*",
            identity.key_id or "key:*",
            identity.principal or "principal:*",
        )
    )
    cache_key = f"{namespace}:{nonce}"
    try:
        claimed = (replay_store or _LOCAL_NONCE_REPLAY_STORE).claim(
            cache_key,
            timestamp_seconds=timestamp_seconds,
            ttl_seconds=max_age,
        )
    except Exception:
        return ("nonce replay backend unavailable",)
    if not claimed:
        return ("replayed request nonce",)
    return ()


def _request_nonce_timestamp(headers: Mapping[str, str], identity: ApiKeyIdentity) -> tuple[str, str]:
    nonce = _header(headers, "x-flow-memory-nonce").strip()
    timestamp = _header(headers, "x-flow-memory-timestamp").strip()
    if not nonce and identity.key_prefix == "bearer" and identity.token_id:
        nonce = f"jwt:{identity.token_id}"
    if not timestamp and identity.key_prefix == "bearer" and identity.issued_at_epoch:
        timestamp = str(identity.issued_at_epoch)
    return nonce, timestamp


def _purge_nonce_cache(*, now: float, max_age_seconds: int) -> None:
    stale_before = now - max_age_seconds
    for key, seen_at in tuple(_NONCE_CACHE.items()):
        if seen_at < stale_before:
            _NONCE_CACHE.pop(key, None)
