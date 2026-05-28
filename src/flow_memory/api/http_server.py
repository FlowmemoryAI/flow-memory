"""Dependency-free local HTTP API server for public-alpha operator testing.

This server intentionally uses the standard library so a fresh clone can expose
Flow Memory's internal router without FastAPI. It is still a local/public-alpha
server, not hardened production infrastructure.
"""

from __future__ import annotations

import ipaddress
import json
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from flow_memory.api.auth import ApiAuthConfig, ApiAuthDecision, LocalNonceReplayStore, NonceReplayStore, RedisNonceReplayStore, authorize_request
from flow_memory.api.audit_middleware import AuditEvent, LocalAuditSink
from flow_memory.api.errors import ApiError, auth_error, error_response, forbidden_error, validation_error
from flow_memory.api.rate_limits import LocalRateLimiter, RateLimitRule
from flow_memory.api.router import LocalApiRouter, create_default_router
from flow_memory.api.request_context import RequestContext
from flow_memory.api.scopes import COMPUTE_BILLING_SCOPE, KNOWN_SCOPES, context_from_headers, require_scopes
from flow_memory.core.types import new_id


@dataclass(frozen=True)
class HttpApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    api_key: str = ""
    api_key_scopes: tuple[str, ...] = tuple(sorted(KNOWN_SCOPES))
    api_key_records: tuple[Mapping[str, Any], ...] = ()
    require_scopes: bool = False
    enable_rate_limit: bool = True
    rate_limit: int = 120
    rate_limit_window_seconds: int = 60
    max_body_bytes: int = 1_048_576
    enable_nonce_check: bool = False
    max_request_age_seconds: int = 300
    jwt_hs256_secret: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = ""
    jwt_leeway_seconds: int = 60
    jwt_require_tenant: bool = False
    nonce_replay_backend: str = "memory"
    nonce_redis_url: str = ""
    nonce_redis_prefix: str = "flow-memory:api"
    nonce_fail_closed: bool = True
    nonce_require_tls: bool = False
    nonce_verify_tls: bool = True
    provider_callback_ip_allowlist: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.port < 0 or self.port > 65535:
            errors.append("port must be 0..65535")
        if self.rate_limit < 1:
            errors.append("rate_limit must be positive")
        if self.rate_limit_window_seconds < 1:
            errors.append("rate_limit_window_seconds must be positive")
        if self.max_body_bytes < 1:
            errors.append("max_body_bytes must be positive")
        if self.max_request_age_seconds < 1:
            errors.append("max_request_age_seconds must be positive")
        if self.jwt_leeway_seconds < 0:
            errors.append("jwt_leeway_seconds must be non-negative")
        invalid_api_key_scopes = tuple(scope for scope in self.api_key_scopes if scope not in KNOWN_SCOPES)
        if invalid_api_key_scopes:
            errors.append(f"api_key_scopes contains unknown scopes: {', '.join(invalid_api_key_scopes)}")
        normalized_nonce_backend = self.nonce_replay_backend.strip().lower()
        if normalized_nonce_backend not in {"memory", "in_memory", "redis"}:
            errors.append("nonce_replay_backend must be memory or redis")
        if self.enable_nonce_check and normalized_nonce_backend == "redis":
            if not self.nonce_redis_url:
                errors.append("nonce_redis_url is required when nonce_replay_backend=redis")
            if self.nonce_require_tls and not self.nonce_redis_url.startswith("rediss://"):
                errors.append("nonce_redis_url must be rediss:// when nonce_require_tls=true")
        for item in self.provider_callback_ip_allowlist:
            allowed = item.strip()
            if not allowed:
                errors.append("provider_callback_ip_allowlist entries must be non-empty")
                continue
            try:
                if "/" in allowed:
                    network = ipaddress.ip_network(allowed, strict=False)
                    if network.prefixlen == 0:
                        errors.append("provider_callback_ip_allowlist must not include world-open CIDR ranges")
                else:
                    address = ipaddress.ip_address(allowed)
                    if address.is_unspecified:
                        errors.append("provider_callback_ip_allowlist must not include unspecified IP addresses")
            except ValueError:
                errors.append(f"provider_callback_ip_allowlist entry must be an IP address or CIDR: {allowed}")
        return tuple(errors)


@dataclass(frozen=True)
class HttpApiResponse:
    status: int
    body: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=dict)
    raw_body: bytes | None = None

    def to_bytes(self) -> bytes:
        if self.raw_body is not None:
            return self.raw_body
        return json.dumps(self.body, indent=2, sort_keys=True, default=str).encode("utf-8")


@dataclass
class HttpApiGateway:
    router: LocalApiRouter = field(default_factory=create_default_router)
    config: HttpApiConfig = field(default_factory=HttpApiConfig)
    audit_sink: LocalAuditSink = field(default_factory=LocalAuditSink)
    limiter: LocalRateLimiter | None = None
    nonce_replay_store: NonceReplayStore | None = None

    def __post_init__(self) -> None:
        errors = self.config.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if self.limiter is None:
            self.limiter = LocalRateLimiter(
                RateLimitRule(self.config.rate_limit, self.config.rate_limit_window_seconds)
            )
        if self.config.enable_nonce_check and self.nonce_replay_store is None:
            self.nonce_replay_store = _nonce_replay_store_from_config(self.config)

    def handle(self, method: str, target: str, headers: Mapping[str, str] | None = None, body: bytes = b"") -> HttpApiResponse:
        header_map = {str(key): str(value) for key, value in (headers or {}).items()}
        request_id = _header(header_map, "x-request-id") or new_id("request")
        split_target = urlsplit(target)
        path = split_target.path or "/"
        context = context_from_headers(method, path, header_map)
        context = context.__class__(
            method=context.method,
            path=context.path,
            request_id=request_id,
            principal=context.principal,
            scopes=context.scopes,
            client_id=context.client_id,
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
        )
        if context.method in {"GET", "HEAD"} and context.path == "/healthz":
            return HttpApiResponse(
                status=200,
                body={
                    "ok": True,
                    "data": {"ok": True, "service": "flow-memory", "endpoint": "healthz"},
                    "request_id": request_id,
                },
                headers=_headers(request_id),
            )
        if context.method in {"GET", "HEAD"} and context.path == "/":
            return HttpApiResponse(
                status=200,
                body={
                    "ok": True,
                    "data": {
                        "service": "Flow Memory Compute Market",
                        "status": "public_level_1_api_live",
                        "auth": "API key or JWT bearer required for /compute/* endpoints",
                        "safe_mode": {
                            "dry_run_required": True,
                            "live_settlement_enabled": False,
                            "broadcast_enabled": False,
                            "private_key_inputs_allowed": False,
                            "funds_moved": False,
                        },
                        "endpoints": {
                            "health": "/compute/health",
                            "readiness": "/compute/readiness",
                            "plan": "/compute/plan",
                            "audit_verify": "/compute/audit/verify",
                            "metrics": "/metrics",
                            "alerts": "/compute/alerts",
                        },
                    },
                    "request_id": request_id,
                },
                headers=_headers(request_id),
            )
        try:
            payload = self._parse_body(method, body)
            query_payload = _query_payload(split_target.query)
            if query_payload:
                payload = {**query_payload, **dict(payload)}
            api_key_records = self.config.api_key_records
            if self.router.api_key_records:
                api_key_records = (*api_key_records, *tuple(self.router.api_key_records.values()))
            stripe_webhook_auth = _stripe_webhook_signature_auth_decision(
                context.method,
                context.path,
                payload,
                header_map,
                body,
            )
            auth = stripe_webhook_auth or authorize_request(
                header_map,
                ApiAuthConfig(
                    api_key=self.config.api_key,
                    api_key_scopes=self.config.api_key_scopes,
                    api_key_records=api_key_records,
                    enable_nonce_check=self.config.enable_nonce_check,
                    max_request_age_seconds=self.config.max_request_age_seconds,
                    jwt_hs256_secret=self.config.jwt_hs256_secret,
                    jwt_issuer=self.config.jwt_issuer,
                    jwt_audience=self.config.jwt_audience,
                    jwt_leeway_seconds=self.config.jwt_leeway_seconds,
                    jwt_require_tenant=self.config.jwt_require_tenant,
                    nonce_replay_store=self.nonce_replay_store,
                ),
                method=context.method,
                path=context.path,
                payload=payload,
            )
            credential_resolved = bool(auth.key_id or auth.principal)
            global_admin_credential = "api:admin" in auth.scopes or "compute:admin" in auth.scopes
            if (
                auth.ok
                and credential_resolved
                and context.tenant_id
                and not auth.tenant_id
                and auth.key_id != "legacy"
                and not global_admin_credential
            ):
                raise forbidden_error(
                    "API key is not bound to the requested tenant",
                    details={"key_id": auth.key_id, "requested_tenant_id": context.tenant_id},
                )
            if (
                auth.ok
                and credential_resolved
                and context.tenant_id
                and auth.tenant_id
                and context.tenant_id != auth.tenant_id
            ):
                raise forbidden_error(
                    "API key tenant does not match the requested tenant",
                    details={
                        "key_id": auth.key_id,
                        "tenant_id": auth.tenant_id,
                        "requested_tenant_id": context.tenant_id,
                    },
                )
            if auth.ok and credential_resolved and auth.workspace_id and context.workspace_id and auth.workspace_id != context.workspace_id:
                raise forbidden_error(
                    "API key workspace does not match the requested workspace",
                    details={
                        "key_id": auth.key_id,
                        "workspace_id": auth.workspace_id,
                        "requested_workspace_id": context.workspace_id,
                    },
                )
            requested_scopes = context.scopes
            if auth.ok and credential_resolved and requested_scopes:
                unauthorized_scopes = tuple(sorted(set(requested_scopes) - set(auth.scopes)))
                if unauthorized_scopes:
                    raise forbidden_error(
                        "Requested API scopes are not granted to this credential",
                        details={
                            "requested": tuple(sorted(requested_scopes)),
                            "granted": tuple(sorted(auth.scopes)),
                            "unauthorized": unauthorized_scopes,
                            "key_id": auth.key_id,
                        },
                    )
            if auth.ok and (auth.scopes or auth.tenant_id or auth.workspace_id or auth.principal):
                resolved_tenant_id = auth.tenant_id or (context.tenant_id if auth.key_id == "legacy" or global_admin_credential else "")
                resolved_workspace_id = auth.workspace_id or context.workspace_id
                effective_scopes = requested_scopes if requested_scopes else (() if auth.key_id == "legacy" and self.config.require_scopes else auth.scopes)
                context = context.__class__(
                    method=context.method,
                    path=context.path,
                    request_id=context.request_id,
                    principal=auth.principal or context.principal,
                    scopes=tuple(sorted(effective_scopes)),
                    client_id=context.client_id,
                    tenant_id=resolved_tenant_id,
                    workspace_id=resolved_workspace_id,
                )
            if not auth.ok:
                raise auth_error("API authorization failed", details={"reasons": auth.reasons})
            if auth.scopes:
                scope_decision = require_scopes(context)
                if not scope_decision.ok and scope_decision.error is not None:
                    raise scope_decision.error
            elif self.config.require_scopes:
                scope_decision = require_scopes(context)
                if not scope_decision.ok and scope_decision.error is not None:
                    raise scope_decision.error
            if self.config.enable_rate_limit and self.limiter is not None:
                rate_decision = self.limiter.check(context, now=int(time.time()))
                if not rate_decision.ok and rate_decision.error is not None:
                    raise rate_decision.error
            router_payload = _tenant_scoped_payload(context, payload)
            router_payload = _inject_provider_callback_ip(context.method, context.path, router_payload, header_map)
            _enforce_provider_callback_ip_allowlist(
                context.method,
                context.path,
                router_payload,
                self.config.provider_callback_ip_allowlist,
            )
            router_payload = _inject_stripe_webhook_context(context.method, context.path, router_payload, header_map, body)
            if context.method in {"GET", "HEAD"} and context.path == "/metrics":
                result = self.router.dispatch("GET", "/compute/metrics", router_payload)
                metrics_text = str(result.get("metrics", "")) if isinstance(result, Mapping) else ""
                content_type = str(result.get("content_type", "text/plain; version=0.0.4")) if isinstance(result, Mapping) else "text/plain; version=0.0.4"
                self.audit_sink.record(_audit_event(context, True, 200, ""))
                return HttpApiResponse(
                    status=200,
                    body={"ok": True, "request_id": request_id},
                    headers={**_headers(request_id), "content-type": content_type},
                    raw_body=metrics_text.encode("utf-8"),
                )
            result = self.router.dispatch(context.method, context.path, router_payload)
            self.audit_sink.record(_audit_event(context, True, 200, ""))
            return HttpApiResponse(
                status=200,
                body={"ok": True, "data": result, "request_id": request_id},
                headers=_headers(request_id),
            )
        except ApiError as exc:
            self.audit_sink.record(_audit_event(context, False, exc.status, exc.code))
            return HttpApiResponse(exc.status, error_response(exc, request_id=request_id), _headers(request_id))
        except (LookupError, KeyError) as exc:
            error = validation_error(str(exc), details={"path": context.path, "method": context.method})
            self.audit_sink.record(_audit_event(context, False, 404, error.code))
            return HttpApiResponse(404, error_response(ApiError(error.code, error.message, 404, error.details), request_id=request_id), _headers(request_id))
        except (ValueError, json.JSONDecodeError) as exc:
            error = validation_error(str(exc))
            self.audit_sink.record(_audit_event(context, False, 400, error.code))
            return HttpApiResponse(400, error_response(error, request_id=request_id), _headers(request_id))
        except Exception as exc:  # pragma: no cover - defensive local server boundary
            error = ApiError("internal.error", "Internal server error", 500, {"type": type(exc).__name__})
            self.audit_sink.record(_audit_event(context, False, 500, error.code))
            return HttpApiResponse(500, error_response(error, request_id=request_id), _headers(request_id))

    def _parse_body(self, method: str, body: bytes) -> Mapping[str, Any]:
        if len(body) > self.config.max_body_bytes:
            raise ValueError("request body exceeds configured maximum")
        if method.upper() in {"GET", "HEAD", "OPTIONS"} or not body:
            return {}
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("JSON request body must be an object")
        return payload


def create_http_server(gateway: HttpApiGateway | None = None, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    resolved_gateway = gateway or HttpApiGateway(config=HttpApiConfig(host=host, port=port))

    class Handler(BaseHTTPRequestHandler):
        server_version = "FlowMemoryLocalHTTP/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            self._handle()

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name
            self._handle()

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib method name
            self._handle()

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib method name
            self._handle(head_only=True)

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def _handle(self, *, head_only: bool = False) -> None:
            length = int(self.headers.get("content-length", "0") or "0")
            body = self.rfile.read(length) if length else b""
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() != "x-flow-memory-client-ip"
            }
            headers["x-flow-memory-client-ip"] = str(self.client_address[0])
            response = resolved_gateway.handle(self.command, self.path, headers, body)
            payload = response.to_bytes()
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)

    server = ThreadingHTTPServer((host, port), Handler)
    server.gateway = resolved_gateway  # type: ignore[attr-defined]
    return server


def serve_local_api(config: HttpApiConfig | None = None) -> None:
    config = config or HttpApiConfig()
    server = create_http_server(HttpApiGateway(config=config), host=config.host, port=config.port)
    server.serve_forever()


def _nonce_replay_store_from_config(config: HttpApiConfig) -> NonceReplayStore:
    backend = config.nonce_replay_backend.strip().lower()
    if backend in {"memory", "in_memory"}:
        return LocalNonceReplayStore()
    return RedisNonceReplayStore(
        config.nonce_redis_url,
        prefix=config.nonce_redis_prefix,
        fail_closed=config.nonce_fail_closed,
        require_tls=config.nonce_require_tls,
        verify_tls=config.nonce_verify_tls,
    )

def _headers(request_id: str) -> dict[str, str]:
    return {"content-type": "application/json; charset=utf-8", "x-request-id": request_id}

def _query_payload(query: str) -> Mapping[str, Any]:
    if not query:
        return {}
    parsed = parse_qs(query, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _tenant_scoped_payload(context: RequestContext, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    tenant_id = str(context.tenant_id or "").strip()
    workspace_id = str(context.workspace_id or "").strip()
    if ("api:admin" in context.scopes or "compute:admin" in context.scopes) and not tenant_id and not workspace_id:
        return payload
    if not tenant_id and not workspace_id:
        return payload
    explicit_tenant = str(payload.get("tenant_id", "")).strip()
    if tenant_id and explicit_tenant and explicit_tenant != tenant_id:
        raise forbidden_error(
            "Authenticated tenant cannot access another tenant",
            details={"tenant_id": tenant_id, "requested_tenant_id": explicit_tenant},
        )
    explicit_workspace = str(payload.get("workspace_id", "")).strip()
    if workspace_id and explicit_workspace and explicit_workspace != workspace_id:
        raise forbidden_error(
            "Authenticated workspace cannot access another workspace",
            details={"workspace_id": workspace_id, "requested_workspace_id": explicit_workspace},
        )
    scoped = {**dict(payload), "_flow_memory_principal": str(context.principal or "")}
    if tenant_id:
        scoped["tenant_id"] = tenant_id
    if workspace_id:
        scoped["workspace_id"] = workspace_id
    return scoped


_PROVIDER_CALLBACK_IP_PATH_SUFFIXES = ("/receipt", "/complete", "/fail", "/heartbeat")
_PROVIDER_CALLBACK_IP_EXACT_PATHS = ("/market/quotes/ingest",)

def _inject_provider_callback_ip(method: str, path: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> Mapping[str, Any]:
    if not _is_provider_callback_path(method, path):
        return payload
    client_ip = _trusted_client_ip(headers)
    if not client_ip:
        return payload
    return {**dict(payload), "_flow_memory_client_ip": client_ip}


def _enforce_provider_callback_ip_allowlist(
    method: str,
    path: str,
    payload: Mapping[str, Any],
    allowlist: tuple[str, ...],
) -> None:
    if not allowlist or not _is_provider_callback_path(method, path):
        return
    client_ip = str(payload.get("_flow_memory_client_ip", ""))
    if _provider_callback_ip_allowed(client_ip, allowlist):
        return
    callback_action = path.rstrip("/").rsplit("/", 1)[-1]
    raise forbidden_error(
        "Provider callback source IP is not allowlisted",
        details={
            "callback_action": callback_action,
            "client_ip": client_ip,
            "allowlist_configured": True,
        },
    )


def _is_provider_callback_path(method: str, path: str) -> bool:
    normalized_method = method.upper()
    return normalized_method == "POST" and (
        path in _PROVIDER_CALLBACK_IP_EXACT_PATHS
        or (path.startswith("/compute/jobs/") and path.endswith(_PROVIDER_CALLBACK_IP_PATH_SUFFIXES))
    )


def _provider_callback_ip_allowed(client_ip: str, allowlist: tuple[str, ...]) -> bool:
    candidate_ip = client_ip.strip()
    if not candidate_ip:
        return False
    try:
        parsed_ip = ipaddress.ip_address(candidate_ip)
    except ValueError:
        return False
    for item in allowlist:
        allowed = item.strip()
        if not allowed:
            continue
        try:
            if "/" in allowed:
                if parsed_ip in ipaddress.ip_network(allowed, strict=False):
                    return True
            elif parsed_ip == ipaddress.ip_address(allowed):
                return True
        except ValueError:
            continue
    return False


def _stripe_webhook_signature_auth_decision(
    method: str,
    path: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    body: bytes,
) -> ApiAuthDecision | None:
    if method.upper() != "POST" or path != "/billing/webhooks/stripe":
        return None
    signature = _header(headers, "stripe-signature")
    if "t=" not in signature or "v1=" not in signature:
        return None
    try:
        from flow_memory.compute_market.service import _verify_webhook_signature, default_service
    except Exception:
        return None
    service = default_service()
    secret = service.config.stripe_webhook_secret
    if not secret:
        return None
    raw_event = payload.get("raw_event")
    if not isinstance(raw_event, Mapping) and payload.get("id") and payload.get("type"):
        excluded = {
            "stripe_signature",
            "raw_event_body",
            "webhook_secret",
            "tenant_id",
            "_flow_memory_principal",
        }
        raw_event = {key: value for key, value in payload.items() if key not in excluded}
    if not isinstance(raw_event, Mapping):
        return None
    raw_event_body = str(payload.get("raw_event_body") or body.decode("utf-8", "replace"))
    if not raw_event_body:
        return None
    if not _verify_webhook_signature(
        raw_event,
        secret,
        signature,
        raw_event_body=raw_event_body,
        tolerance_seconds=service.config.stripe_webhook_tolerance_seconds,
    ):
        return None
    return ApiAuthDecision(
        ok=True,
        principal="stripe-webhook",
        scopes=(COMPUTE_BILLING_SCOPE,),
        key_id="stripe-signature",
    )

def _inject_stripe_webhook_context(method: str, path: str, payload: Mapping[str, Any], headers: Mapping[str, str], body: bytes) -> Mapping[str, Any]:
    if method.upper() != "POST" or path != "/billing/webhooks/stripe":
        return payload
    enriched = dict(payload)
    signature = _header(headers, "stripe-signature")
    if signature and not enriched.get("stripe_signature"):
        enriched["stripe_signature"] = signature
    if "raw_event" not in enriched and enriched.get("id") and enriched.get("type"):
        excluded = {"stripe_signature", "raw_event_body", "webhook_secret", "tenant_id", "_flow_memory_principal"}
        raw_event = {key: value for key, value in enriched.items() if key not in excluded}
        enriched["raw_event"] = raw_event
        if body and not enriched.get("raw_event_body"):
            enriched["raw_event_body"] = body.decode("utf-8", "replace")
    return enriched


def _trusted_client_ip(headers: Mapping[str, str]) -> str:
    direct = _header(headers, "x-flow-memory-client-ip")
    if direct:
        return direct
    forwarded = _header(headers, "x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return _header(headers, "x-real-ip")


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value.strip()
    return ""


def _audit_event(context: RequestContext, ok: bool, status: int, error_code: str) -> AuditEvent:

    return AuditEvent(
        method=context.method,
        path=context.path,
        principal=context.principal,
        request_id=context.request_id,
        ok=ok,
        status=status,
        error_code=error_code,
        tenant_id=context.tenant_id,
    )
